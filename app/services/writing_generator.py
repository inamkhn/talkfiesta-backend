import logging
import json
from google import genai
from google.genai import types

from app.core.celery_app import celery_app
from app.db.session import SessionLocal
from app.models.user import User
from app.models.writing import WritingPrompt
from app.config import settings

logger = logging.getLogger(__name__)

@celery_app.task(name="app.services.writing_generator.generate_cycle_writing_prompts")
def generate_cycle_writing_prompts(user_id: str, cycle: int):
    """
    Dynamically generates 21 personalized writing prompts for a user's cycle using Google Gemini.
    Triggered silently in background when a user starts a cycle.
    """
    logger.info(f"Starting async writing prompts generation for User {user_id}, Cycle {cycle}")
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
        Generate exactly 21 writing prompts for a user learning English.
        User Level: {user_level}.
        Learning Goal: {learning_goal}.
        Cycle Number: {cycle}.
        
        The 21 prompts MUST be logically progressive across exactly 21 days (1 prompt per day).
        Ensure the topics are engaging, relevant to their learning goal, and appropriately challenging for their CEFR level.
        Return a strict JSON ARRAY of EXACTLY 21 objects. Each object MUST have:
        - "day": integer (1 through 21)
        - "title": string (A short, catchy title for the writing task)
        - "prompt": string (The detailed writing instruction/scenario)
        - "min_words": integer (Reasonable minimum length for {user_level}, e.g. 50-100)
        - "max_words": integer (Reasonable maximum length for {user_level}, e.g. 150-300)
        - "grammar_focus": string (e.g. "Past Perfect", "Conditionals", "Business Vocabulary")
        - "difficulty": string (Must exactly be "{user_level}")
        - "tips": array of exactly 3 string tips to help them write a good response
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
        
        # Strip markdown fences if present
        if raw_text.startswith("```json"):
            raw_text = raw_text[7:]
        if raw_text.endswith("```"):
            raw_text = raw_text[:-3]
            
        prompts_data = json.loads(raw_text.strip())
        
        if len(prompts_data) != 21:
            logger.warning(f"Gemini returned {len(prompts_data)} prompts instead of 21. Proceeding with what we have.")
            
        db_prompts = []
        for prompt_dict in prompts_data:
            db_prompt = WritingPrompt(
                user_id=user.id,
                cycle=cycle,
                day=prompt_dict.get('day', 1),
                title=prompt_dict.get('title', 'Daily Writing Practice'),
                prompt=prompt_dict.get('prompt', 'Write about your day.'),
                min_words=prompt_dict.get('min_words', 50),
                max_words=prompt_dict.get('max_words', 300),
                grammar_focus=prompt_dict.get('grammar_focus', ''),
                difficulty=prompt_dict.get('difficulty', user_level),
                tips=prompt_dict.get('tips', [])
            )
            db_prompts.append(db_prompt)
            
        db.bulk_save_objects(db_prompts)
        db.commit()
        logger.info(f"Successfully generated and saved {len(db_prompts)} dynamic writing prompts for User {user_id}")

    except Exception as e:
        logger.error(f"Error generating writing prompts for User {user_id}: {e}", exc_info=True)
        db.rollback()
    finally:
        db.close()
