import logging
import json
import time
from google import genai
from google.genai import types

from app.core.celery_app import celery_app
from app.db.session import SessionLocal
from app.models.user import User
from app.models.vocabulary import VocabularyWord, VocabularyProgress
from app.config import settings

logger = logging.getLogger(__name__)


def _generate_batch(client, user, cycle: int, day_start: int, day_end: int, struggle_context: str) -> list:
    """Call Gemini to generate 10 words/day for days day_start..day_end (inclusive)."""
    num_days = day_end - day_start + 1
    total_words = num_days * 10

    prompt = f"""
    You are a highly skilled CEFR native English curriculum expert.
    Generate exactly {total_words} vocabulary words for a user learning English.
    User Level: {user.english_level or 'B1'}.
    Learning Goal: {user.learning_goal or 'conversational'}.
    Cycle Number: {cycle}.

    {struggle_context}

    Organize the words into exactly {num_days} days (days {day_start} to {day_end}), 10 words per day.
    Return a strict JSON ARRAY of EXACTLY {total_words} objects. Each object MUST have:
    - "word": string
    - "phonetic": string (IPA)
    - "part_of_speech": string
    - "definition": string
    - "example_sentences": array of exactly 3 string examples
    - "synonyms": array of strings (max 3)
    - "antonyms": array of strings (max 3)
    - "collocations": array of strings (max 3 common pairings)
    - "memory_tip": string mnemonic device
    - "difficulty": string CEFR level
    - "day": integer ({day_start} through {day_end})
    - "position_in_day": integer (1 through 10)
    """

    # Retry up to 4 times with exponential backoff for 503 / transient errors
    # Priority: gemini-2.5-flash-lite (stable) -> gemini-flash-latest -> gemini-2.5-flash
    models_to_try = ["gemini-2.5-flash-lite", "gemini-flash-latest", "gemini-2.5-flash"]
    last_error = None

    for attempt in range(4):
        model = models_to_try[min(attempt, len(models_to_try) - 1)]
        try:
            response = client.models.generate_content(
                model=model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=0.7
                )
            )
            raw_text = response.text.strip()

            # Strip markdown fences if present
            if raw_text.startswith("```json"):
                raw_text = raw_text[7:]
            if raw_text.endswith("```"):
                raw_text = raw_text[:-3]

            words_data = json.loads(raw_text.strip())
            logger.info(f"Batch days {day_start}-{day_end}: got {len(words_data)} words via {model}")
            return words_data

        except Exception as e:
            last_error = e
            wait = 5 * (2 ** attempt)  # 5s, 10s, 20s, 40s
            logger.warning(f"Batch days {day_start}-{day_end} attempt {attempt + 1} ({model}) failed: {e}. Retrying in {wait}s...")
            time.sleep(wait)

    raise RuntimeError(f"All retries failed for batch days {day_start}-{day_end}: {last_error}")


@celery_app.task(name="app.services.vocabulary_generator.generate_cycle_vocabulary")
def generate_cycle_vocabulary(user_id: str, cycle: int):
    """
    Dynamically generates 210 personalized words for a user's cycle using Google Gemini.
    Uses 3 batched API calls (70 words each) to avoid response truncation.
    Triggered when a user starts a new plan (cycle).
    """
    logger.info(f"Starting async vocabulary generation for User {user_id}, Cycle {cycle}")
    db = SessionLocal()
    client = genai.Client(api_key=settings.GOOGLE_AI_STUDIO_API_KEY)

    try:
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            logger.error(f"User {user_id} not found.")
            return

        # Fetch words user struggled with to reinforce word families
        struggled_progress = db.query(VocabularyProgress).join(VocabularyWord).filter(
            VocabularyProgress.user_id == user_id,
            VocabularyProgress.mastery_level < 3
        ).order_by(VocabularyProgress.times_practiced.desc()).limit(20).all()

        struggled_words = [p.word.word for p in struggled_progress]
        struggle_context = (
            f"Please reinforce word families for these words they struggled with recently: {', '.join(struggled_words)}"
            if struggled_words else ""
        )

        # Generate in 3 batches to stay within Gemini output token limits:
        # Batch 1: days 1-7 (70 words)
        # Batch 2: days 8-14 (70 words)
        # Batch 3: days 15-21 (70 words)
        batches = [(1, 7), (8, 14), (15, 21)]
        all_words_data = []

        for day_start, day_end in batches:
            logger.info(f"Calling Gemini for batch: days {day_start}-{day_end}...")
            try:
                batch = _generate_batch(client, user, cycle, day_start, day_end, struggle_context)
                all_words_data.extend(batch)
            except json.JSONDecodeError as e:
                logger.error(f"JSON parse error in batch days {day_start}-{day_end}: {e}")
                raise
            except Exception as e:
                logger.error(f"Error in batch days {day_start}-{day_end}: {e}")
                raise

        logger.info(f"Total words collected across all batches: {len(all_words_data)}")

        db_words = []
        for word_dict in all_words_data:
            db_word = VocabularyWord(
                user_id=user.id,
                cycle=cycle,
                day=word_dict.get('day', 1),
                position_in_day=word_dict.get('position_in_day', 1),
                word=word_dict.get('word', ''),
                phonetic=word_dict.get('phonetic', ''),
                part_of_speech=word_dict.get('part_of_speech', ''),
                definition=word_dict.get('definition', ''),
                example_sentences=word_dict.get('example_sentences', []),
                synonyms=word_dict.get('synonyms', []),
                antonyms=word_dict.get('antonyms', []),
                collocations=word_dict.get('collocations', []),
                memory_tip=word_dict.get('memory_tip', ''),
                difficulty=word_dict.get('difficulty', user.english_level or 'B1')
            )
            db_words.append(db_word)

        db.bulk_save_objects(db_words)
        db.commit()
        logger.info(f"Successfully generated and saved {len(db_words)} dynamic words for User {user_id}")

    except Exception as e:
        logger.error(f"Error generating vocabulary for User {user_id}: {e}", exc_info=True)
        db.rollback()
    finally:
        db.close()
