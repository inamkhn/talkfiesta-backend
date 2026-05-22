import logging
from typing import List, Optional
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import func
from fastapi import HTTPException
from google import genai
from google.genai import types

from app.config import settings
from app.models.user import User
from app.models.plan import UserPlan
from app.models.writing import WritingPrompt, WritingSubmission
from app.schemas.writing import WritingSubmitRequest

logger = logging.getLogger(__name__)

def get_daily_prompts(db: Session, cycle: int, day: int, user_level: str):
    prompts = db.query(WritingPrompt).filter(
        WritingPrompt.cycle == cycle,
        WritingPrompt.day == day,
        WritingPrompt.difficulty == user_level
    ).all()
    
    if not prompts:
        prompts = db.query(WritingPrompt).filter(
            WritingPrompt.cycle == cycle,
            WritingPrompt.day == day
        ).all()
    return prompts

def get_prompt_by_id(db: Session, prompt_id: str):
    prompt = db.query(WritingPrompt).filter(WritingPrompt.id == prompt_id).first()
    if not prompt:
        raise HTTPException(status_code=404, detail="Prompt not found")
    return prompt

def grade_and_save_submission(db: Session, current_user: User, payload: WritingSubmitRequest):
    prompt = db.query(WritingPrompt).filter(WritingPrompt.id == payload.prompt_id).first()
    if not prompt:
        raise HTTPException(status_code=404, detail="Prompt not found")

    word_count = len(payload.content.split())
    if word_count < prompt.min_words:
        raise HTTPException(
            status_code=400,
            detail=f"Submission too short. Minimum {prompt.min_words} words required, got {word_count}."
        )

    # ── Gemini Grading ───────────────────────────────────────────────────────
    try:
        client = genai.Client(api_key=settings.GOOGLE_AI_STUDIO_API_KEY)
        grading_prompt = f"""
        You are an expert CEFR English writing assessor.
        User Level: {current_user.english_level or 'B1'}.
        Writing Prompt they were given: "{prompt.prompt}"
        Grammar Focus: {prompt.grammar_focus or 'General'}.
        User's Submission ({word_count} words):
        ---
        {payload.content}
        ---
        Grade this writing submission. Return ONLY a strict JSON object with these exact keys:
        {{
          "overall_score": <integer 0-100>,
          "grammar_score": <integer 0-100>,
          "vocabulary_score": <integer 0-100>,
          "coherence_score": <integer 0-100>,
          "grammar_errors": [
            {{"text": "<wrong text>", "suggestion": "<corrected text>", "message": "<why it's wrong>", "offset": 0, "length": 0}}
          ],
          "vocabulary_suggestions": [
            {{"original": "<basic word used>", "suggestion": "<better word>", "reason": "<why it's better>"}}
          ],
          "feedback": "<detailed paragraph feedback>",
          "improvement_tips": ["<tip 1>", "<tip 2>", "<tip 3>"],
          "encouragement": "<one short motivational sentence>"
        }}
        """
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=grading_prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0.3
            )
        )
        import json
        raw = response.text.strip()
        if raw.startswith("```json"):
            raw = raw[7:]
        if raw.endswith("```"):
            raw = raw[:-3]
        ai = json.loads(raw.strip())
    except Exception as e:
        logger.error(f"Gemini grading failed: {e}", exc_info=True)
        ai = {}  # Graceful degradation — save ungraded submission

    overall = ai.get("overall_score")
    passed = (overall >= 60) if overall else False
    xp = 15 if passed else 5

    submission = WritingSubmission(
        user_id=current_user.id,
        prompt_id=payload.prompt_id,
        content=payload.content,
        word_count=word_count,
        overall_score=overall,
        grammar_score=ai.get("grammar_score"),
        vocabulary_score=ai.get("vocabulary_score"),
        coherence_score=ai.get("coherence_score"),
        grammar_errors=ai.get("grammar_errors", []),
        vocabulary_suggestions=ai.get("vocabulary_suggestions", []),
        feedback=ai.get("feedback"),
        improvement_tips=ai.get("improvement_tips", []),
        encouragement=ai.get("encouragement"),
        passed=passed,
        xp_earned=xp,
        analysed_at=datetime.utcnow() if ai else None
    )
    db.add(submission)
    db.commit()
    db.refresh(submission)

    # Award XP to user
    if xp > 0:
        current_user.total_xp = (current_user.total_xp or 0) + xp
        db.commit()

    # --- Day-completion tracking ---
    if (
        prompt.user_id == current_user.id
        and prompt.day == current_user.current_day
        and current_user.active_plan_id
    ):
        plan = db.query(UserPlan).filter(
            UserPlan.id == current_user.active_plan_id
        ).first()
        if plan and prompt.cycle == plan.cycle_number:
            from app.models.plan import DailyProgress
            day_prog = (
                db.query(DailyProgress)
                .filter(
                    DailyProgress.plan_id == current_user.active_plan_id,
                    DailyProgress.day_number == current_user.current_day,
                )
                .first()
            )
            if day_prog and not day_prog.writing_done:
                day_prog.writing_done = True
                day_prog.activities_completed = (
                    day_prog.activities_completed or 0
                ) + 1
                db.commit()
                from app.services.progress_service import advance_day_if_complete
                advance_day_if_complete(db, current_user)

    return submission

def revise_submission(db: Session, current_user: User, submission_id: str, payload: WritingSubmitRequest):
    original = db.query(WritingSubmission).filter(
        WritingSubmission.id == submission_id,
        WritingSubmission.user_id == current_user.id
    ).first()
    if not original:
        raise HTTPException(status_code=404, detail="Submission not found")

    revised_payload = WritingSubmitRequest(
        prompt_id=original.prompt_id,
        content=payload.content
    )
    new_sub = grade_and_save_submission(db, current_user, revised_payload)
    
    db.query(WritingSubmission).filter(WritingSubmission.id == new_sub.id).update(
        {"is_revised": True, "revision_of": submission_id}
    )
    original.is_revised = True
    db.commit()
    return new_sub

def get_user_submissions(db: Session, current_user: User):
    return db.query(WritingSubmission).filter(
        WritingSubmission.user_id == current_user.id
    ).order_by(WritingSubmission.created_at.desc()).limit(50).all()

def get_submission_detail(db: Session, current_user: User, submission_id: str):
    sub = db.query(WritingSubmission).filter(
        WritingSubmission.id == submission_id,
        WritingSubmission.user_id == current_user.id
    ).first()
    if not sub:
        raise HTTPException(status_code=404, detail="Submission not found")
    return sub

def get_writing_analytics(db: Session, current_user: User):
    total = db.query(func.count(WritingSubmission.id)).filter(WritingSubmission.user_id == current_user.id).scalar() or 0
    passed = db.query(func.count(WritingSubmission.id)).filter(WritingSubmission.user_id == current_user.id, WritingSubmission.passed == True).scalar() or 0
    avg_score = db.query(func.avg(WritingSubmission.overall_score)).filter(WritingSubmission.user_id == current_user.id).scalar()
    return {
        "total_submissions": total,
        "submissions_passed": passed,
        "average_overall_score": round(float(avg_score), 1) if avg_score else 0.0,
        "pass_rate_percent": round((passed / total) * 100, 1) if total else 0.0
    }
