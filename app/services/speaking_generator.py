import logging
import json
from google import genai
from google.genai import types

from app.core.celery_app import celery_app
from app.db.session import SessionLocal
from app.models.user import User
from app.models.speaking import SpeakingExercise
from app.config import settings

logger = logging.getLogger(__name__)

@celery_app.task(name="app.services.speaking_generator.generate_cycle_speaking_exercises")
def generate_cycle_speaking_exercises(user_id: str, cycle: int):
    """
    Dynamically generates 21 personalized speaking exercises for a user's cycle using Google Gemini.
    Triggered silently in background when a user starts a cycle.
    """
    logger.info(f"Starting async speaking exercise generation for User {user_id}, Cycle {cycle}")
    db = SessionLocal()
    client = genai.Client(api_key=settings.GOOGLE_AI_STUDIO_API_KEY)
    
    try:
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            logger.error(f"User {user_id} not found.")
            return

        user_level = user.english_level or 'B1'
        learning_goal = user.learning_goal or 'conversational'

        prompt = f"""
        You are a highly skilled CEFR native English curriculum expert.
        Generate exactly 21 speaking exercises for a user learning English.
        User Level: {user_level}.
        Learning Goal: {learning_goal}.
        Cycle Number: {cycle}.
        
        The 21 exercises MUST be logically progressive across exactly 21 days (1 exercise per day).
        Ensure the topics are highly engaging, relevant to their learning goal, and appropriately challenging for their CEFR level.
        Return a strict JSON ARRAY of EXACTLY 21 objects. Each object MUST have:
        - "day": integer (1 through 21)
        - "title": string (A short, catchy title for the speaking task)
        - "instruction": string (The context or roleplay setup, e.g. "You are at a hotel reception...")
        - "prompt_text": string (The exact question or prompt they need to answer/speak about)
        - "duration_seconds": integer (Suggested duration, e.g., 60-120 seconds)
        - "difficulty": string (Must exactly be "{user_level}")
        - "tips": array of exactly 3 string tips (vocabulary to use, tone, etc.)
        """
        
        logger.info("Calling Gemini API... this generation may take 15-30 seconds.")
        response = client.models.generate_content(
            model="gemini-3-flash-preview",
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0.7
            )
        )
        raw_text = response.text.strip()
        
        if raw_text.startswith("```json"):
            raw_text = raw_text[7:]
        if raw_text.endswith("```"):
            raw_text = raw_text[:-3]
            
        prompts_data = json.loads(raw_text.strip())
        
        if len(prompts_data) != 21:
            logger.warning(f"Gemini returned {len(prompts_data)} speaking exercises instead of 21. Proceeding with what we have.")
            
        db_exercises = []
        for prompt_dict in prompts_data:
            db_exercise = SpeakingExercise(
                user_id=user.id,
                cycle=cycle,
                day=prompt_dict.get('day', 1),
                title=prompt_dict.get('title', 'Daily Speaking Practice'),
                instruction=prompt_dict.get('instruction', 'Read the prompt and speak.'),
                prompt_text=prompt_dict.get('prompt_text', 'Introduce yourself.'),
                duration_seconds=prompt_dict.get('duration_seconds', 60),
                difficulty=prompt_dict.get('difficulty', user_level),
                tips=prompt_dict.get('tips', [])
            )
            db_exercises.append(db_exercise)
            
        db.bulk_save_objects(db_exercises)
        db.commit()
        logger.info(f"Successfully generated and saved {len(db_exercises)} dynamic speaking exercises for User {user_id}")

    except Exception as e:
        logger.error(f"Error generating speaking exercises for User {user_id}: {e}", exc_info=True)
        db.rollback()
    finally:
        db.close()
