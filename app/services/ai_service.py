"""
TalkFiesta — AI Service (Gemini)
=================================
Wraps Google Gemini calls used across the app.

  analyse_speaking()  — grades an audio recording
  grade_writing()     — grades a writing submission (used by writing_service)
"""
import json
import time
import base64
import logging
from typing import Optional
from app.config import settings

logger = logging.getLogger(__name__)

MAX_RETRIES = 3
RETRY_DELAYS = [2, 4, 8]   # exponential back-off in seconds


# ── Lazy client ───────────────────────────────────────────────────────────────

def _get_model(model_name: str = "gemini-1.5-flash"):
    """
    Lazy-import and configure the Gemini SDK.
    Raises RuntimeError if the API key is not set.
    """
    try:
        import google.generativeai as genai
    except ImportError:
        raise RuntimeError(
            "google-generativeai is not installed. Run: pip install google-generativeai"
        )

    if not settings.GOOGLE_AI_STUDIO_API_KEY:
        raise RuntimeError(
            "GOOGLE_AI_STUDIO_API_KEY is not configured. "
            "Set it in .env to enable AI features."
        )

    genai.configure(api_key=settings.GOOGLE_AI_STUDIO_API_KEY)
    return genai.GenerativeModel(model_name)


def _call_with_retry(model, contents: list, generation_config=None) -> str:
    """Call Gemini with exponential back-off on transient errors."""
    for attempt in range(MAX_RETRIES):
        try:
            kwargs = {}
            if generation_config:
                kwargs["generation_config"] = generation_config
            response = model.generate_content(contents, **kwargs)
            return response.text
        except Exception as exc:
            if attempt == MAX_RETRIES - 1:
                raise
            wait = RETRY_DELAYS[attempt]
            logger.warning(
                f"Gemini attempt {attempt + 1} failed: {exc}. Retrying in {wait}s..."
            )
            time.sleep(wait)


def _parse_json_response(raw: str) -> dict:
    """Strip markdown fences and parse JSON from Gemini response."""
    text = raw.strip()
    if text.startswith("```"):
        # Remove opening fence (```json or ```)
        text = text.split("\n", 1)[1] if "\n" in text else text[3:]
    if text.endswith("```"):
        text = text[:-3].strip()
    return json.loads(text)


# ══════════════════════════════════════════════════════════════════════════════
# SPEAKING ANALYSIS
# ══════════════════════════════════════════════════════════════════════════════

SPEAKING_SYSTEM_PROMPT = """
You are an expert CEFR English speaking assessor.
Analyse the provided audio recording and return ONLY a strict JSON object — no prose, no markdown.

JSON schema:
{
  "transcript":           "<full transcript of what was said>",
  "overall_score":        <integer 0-100>,
  "fluency_score":        <integer 0-100>,
  "pronunciation_score":  <integer 0-100>,
  "pace_score":           <integer 0-100>,
  "words_mispronounced":  ["<word>", ...],
  "pronunciation_issues": [{"word": "<word>", "issue": "<description>"}],
  "feedback":             "<2-3 sentence overall feedback paragraph>",
  "improvement_tips":     ["<tip 1>", "<tip 2>", "<tip 3>"],
  "encouragement":        "<one short motivational sentence>",
  "passed":               <true if overall_score >= 60, else false>
}

Scoring guide:
  90-100 = Near-native / excellent
  75-89  = Good, minor issues
  60-74  = Adequate, noticeable issues
  40-59  = Below standard, significant issues
  0-39   = Needs substantial improvement

Be constructive and encouraging. Tailor feedback to the learner's CEFR level.
"""


def analyse_speaking(
    audio_bytes: bytes,
    mime_type: str,
    exercise_text: str,
    level: str = "B1",
) -> dict:
    """
    Send audio to Gemini for speaking analysis.

    Args:
        audio_bytes:   Raw audio file bytes
        mime_type:     MIME type (audio/webm, audio/mp4, etc.)
        exercise_text: The prompt the learner was responding to
        level:         Learner's CEFR level (A1–C2)

    Returns:
        Parsed dict matching the JSON schema above.
    """
    model = _get_model("gemini-1.5-flash")

    # Encode audio as base64 inline data
    audio_b64 = base64.b64encode(audio_bytes).decode("utf-8")

    prompt = (
        f"{SPEAKING_SYSTEM_PROMPT}\n\n"
        f"Learner CEFR level: {level}\n"
        f"Exercise prompt they were responding to: \"{exercise_text}\"\n\n"
        "Analyse the audio recording attached below."
    )

    contents = [
        prompt,
        {
            "inline_data": {
                "mime_type": mime_type,
                "data": audio_b64,
            }
        },
    ]

    try:
        import google.generativeai as genai
        generation_config = genai.types.GenerationConfig(
            temperature=0.2,
            response_mime_type="application/json",
        )
    except Exception:
        generation_config = None

    raw = _call_with_retry(model, contents, generation_config)
    result = _parse_json_response(raw)

    # Clamp scores to 0-100
    for field in ("overall_score", "fluency_score", "pronunciation_score", "pace_score"):
        if field in result and result[field] is not None:
            result[field] = max(0, min(100, int(result[field])))

    # Ensure passed is consistent with overall_score
    if "overall_score" in result:
        result["passed"] = result["overall_score"] >= 60

    return result


# ══════════════════════════════════════════════════════════════════════════════
# WRITING GRADING  (used by writing_service.py)
# ══════════════════════════════════════════════════════════════════════════════

WRITING_SYSTEM_PROMPT = """
You are an expert CEFR English writing assessor.
Grade the submission and return ONLY a strict JSON object — no prose, no markdown.

JSON schema:
{
  "overall_score":            <integer 0-100>,
  "grammar_score":            <integer 0-100>,
  "vocabulary_score":         <integer 0-100>,
  "coherence_score":          <integer 0-100>,
  "grammar_errors":           [{"text": "<original>", "suggestion": "<fix>", "message": "<explanation>"}],
  "vocabulary_suggestions":   [{"original": "<word>", "suggestion": "<better word>", "reason": "<why>"}],
  "feedback":                 "<2-3 sentence overall feedback paragraph>",
  "improvement_tips":         ["<tip 1>", "<tip 2>", "<tip 3>"],
  "encouragement":            "<one short motivational sentence>"
}
"""


def grade_writing(
    content: str,
    prompt_text: str,
    grammar_focus: Optional[str],
    level: str = "B1",
    word_count: int = 0,
) -> dict:
    """
    Send writing submission to Gemini for grading.

    Returns:
        Parsed dict matching the JSON schema above.
    """
    model = _get_model("gemini-1.5-flash")

    prompt = (
        f"{WRITING_SYSTEM_PROMPT}\n\n"
        f"Learner CEFR level: {level}\n"
        f"Writing prompt: \"{prompt_text}\"\n"
        f"Grammar focus: {grammar_focus or 'General'}\n"
        f"Word count: {word_count}\n\n"
        f"Submission:\n---\n{content}\n---"
    )

    try:
        import google.generativeai as genai
        generation_config = genai.types.GenerationConfig(
            temperature=0.2,
            response_mime_type="application/json",
        )
    except Exception:
        generation_config = None

    raw = _call_with_retry(model, [prompt], generation_config)
    result = _parse_json_response(raw)

    # Clamp scores
    for field in ("overall_score", "grammar_score", "vocabulary_score", "coherence_score"):
        if field in result and result[field] is not None:
            result[field] = max(0, min(100, int(result[field])))

    return result
