"""
Admin Service
Handles admin operations for content management
"""

from sqlalchemy.orm import Session
from sqlalchemy import desc, and_
from fastapi import HTTPException, status
from typing import List, Optional
from datetime import datetime
import uuid

from app.models.speaking import SpeakingExercise, DifficultyLevel as SpeakingDifficulty
from app.models.vocabulary import VocabularyWord, PartOfSpeech, DifficultyLevel as VocabularyDifficulty
from app.models.writing import WritingPrompt, PromptType
from app.models.user import User, Role


class AdminService:
    """Service for admin operations"""
    
    def __init__(self, db: Session):
        self.db = db
    
    # ============================================
    # GET ALL USERS
    # ============================================
    
    def get_all_users(
        self,
        role: Optional[Role] = None,
        is_active: Optional[bool] = None,
        limit: int = 20,
        offset: int = 0
    ) -> List[User]:
        """
        Get all users with optional filters
        
        Args:
            role: Filter by role
            is_active: Filter by active status
            limit: Maximum records to return
            offset: Pagination offset
            
        Returns:
            List of User objects
        """
        query = self.db.query(User)
        
        if role is not None:
            query = query.filter(User.role == role)
        
        if is_active is not None:
            query = query.filter(User.is_active == is_active)
        
        # Order by created_at (most recent first)
        users = query.order_by(
            desc(User.created_at)
        ).limit(limit).offset(offset).all()
        
        return users
    
    # ============================================
    # CREATE SPEAKING EXERCISE
    # ============================================
    
    def create_speaking_exercise(
        self,
        day_number: int,
        cycle_number: int,
        difficulty_level: str,
        topic: str,
        prompt_text: str,
        target_duration_seconds: int,
        instructions: str,
        example_response: Optional[str] = None,
        focus_areas: Optional[List[str]] = None,
        learning_resources: Optional[List[dict]] = None
    ) -> SpeakingExercise:
        """
        Create a new speaking exercise
        
        Args:
            day_number: Day number (1-21)
            cycle_number: Cycle number (1-5)
            difficulty_level: BEGINNER, INTERMEDIATE, or ADVANCED
            topic: Exercise topic
            prompt_text: The prompt text
            target_duration_seconds: Target duration in seconds
            instructions: Instructions for the exercise
            example_response: Optional example response
            focus_areas: List of focus areas
            learning_resources: List of learning resources
            
        Returns:
            SpeakingExercise object
            
        Raises:
            HTTPException: If exercise already exists
        """
        # Check if exercise already exists for this day and cycle
        existing = self.db.query(SpeakingExercise).filter(
            and_(
                SpeakingExercise.day_number == day_number,
                SpeakingExercise.cycle_number == cycle_number
            )
        ).first()
        
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Speaking exercise already exists for Day {day_number}, Cycle {cycle_number}"
            )
        
        # Create exercise
        exercise = SpeakingExercise(
            id=str(uuid.uuid4()),
            day_number=day_number,
            cycle_number=cycle_number,
            difficulty_level=difficulty_level,
            topic=topic,
            prompt_text=prompt_text,
            target_duration_seconds=target_duration_seconds,
            instructions=instructions,
            example_response=example_response,
            focus_areas=focus_areas or ["grammar", "fluency", "pronunciation"],
            learning_resources=learning_resources or []
        )
        
        self.db.add(exercise)
        self.db.commit()
        self.db.refresh(exercise)
        
        return exercise
    
    # ============================================
    # CREATE VOCABULARY WORD
    # ============================================
    
    def create_vocabulary_word(
        self,
        word: str,
        definition: str,
        part_of_speech: str,
        difficulty_level: str,
        cefr_level: str,
        cycle_number: int,
        pronunciation_ipa: str,
        pronunciation_audio_url: Optional[str] = None,
        example_sentences: Optional[List[dict]] = None,
        synonyms: Optional[List[str]] = None,
        antonyms: Optional[List[str]] = None,
        usage_tips: Optional[str] = None,
        category: str = "daily"
    ) -> VocabularyWord:
        """
        Create a new vocabulary word
        
        Args:
            word: The word
            definition: Word definition
            part_of_speech: NOUN, VERB, ADJECTIVE, etc.
            difficulty_level: BEGINNER, INTERMEDIATE, or ADVANCED
            cefr_level: A1, A2, B1, B2, C1, C2
            cycle_number: Cycle number (1-5)
            pronunciation_ipa: IPA pronunciation
            pronunciation_audio_url: Optional audio URL
            example_sentences: List of {sentence, translation}
            synonyms: List of synonyms
            antonyms: List of antonyms
            usage_tips: Optional usage tips
            category: Category (daily, academic, business, etc.)
            
        Returns:
            VocabularyWord object
            
        Raises:
            HTTPException: If word already exists
        """
        # Check if word already exists
        existing = self.db.query(VocabularyWord).filter(
            VocabularyWord.word == word
        ).first()
        
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Vocabulary word '{word}' already exists"
            )
        
        # Create word
        word_obj = VocabularyWord(
            id=str(uuid.uuid4()),
            word=word,
            definition=definition,
            part_of_speech=part_of_speech,
            difficulty_level=difficulty_level,
            cefr_level=cefr_level,
            cycle_number=cycle_number,
            pronunciation_ipa=pronunciation_ipa,
            pronunciation_audio_url=pronunciation_audio_url,
            example_sentences=example_sentences or [],
            synonyms=synonyms or [],
            antonyms=antonyms or [],
            usage_tips=usage_tips,
            category=category
        )
        
        self.db.add(word_obj)
        self.db.commit()
        self.db.refresh(word_obj)
        
        return word_obj
    
    # ============================================
    # CREATE WRITING PROMPT
    # ============================================
    
    def create_writing_prompt(
        self,
        day_number: int,
        cycle_number: int,
        difficulty_level: str,
        prompt_title: str,
        prompt_text: str,
        prompt_type: str,
        target_word_count: int,
        time_limit_minutes: Optional[int] = None,
        focus_areas: Optional[List[str]] = None,
        writing_tips: Optional[List[str]] = None,
        sample_outline: Optional[str] = None,
        learning_resources: Optional[List[dict]] = None
    ) -> WritingPrompt:
        """
        Create a new writing prompt
        
        Args:
            day_number: Day number (1-21)
            cycle_number: Cycle number (1-5)
            difficulty_level: BEGINNER, INTERMEDIATE, or ADVANCED
            prompt_title: Prompt title
            prompt_text: Prompt text
            prompt_type: ESSAY, EMAIL, STORY, OPINION, or DESCRIPTION
            target_word_count: Target word count
            time_limit_minutes: Optional time limit in minutes
            focus_areas: List of focus areas
            writing_tips: List of writing tips
            sample_outline: Optional sample outline
            learning_resources: List of learning resources
            
        Returns:
            WritingPrompt object
            
        Raises:
            HTTPException: If prompt already exists
        """
        # Check if prompt already exists for this day and cycle
        existing = self.db.query(WritingPrompt).filter(
            and_(
                WritingPrompt.day_number == day_number,
                WritingPrompt.cycle_number == cycle_number
            )
        ).first()
        
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Writing prompt already exists for Day {day_number}, Cycle {cycle_number}"
            )
        
        # Create prompt
        prompt = WritingPrompt(
            id=str(uuid.uuid4()),
            day_number=day_number,
            cycle_number=cycle_number,
            difficulty_level=difficulty_level,
            prompt_title=prompt_title,
            prompt_text=prompt_text,
            prompt_type=prompt_type,
            target_word_count=target_word_count,
            time_limit_minutes=time_limit_minutes,
            focus_areas=focus_areas or ["grammar", "structure", "vocabulary"],
            writing_tips=writing_tips or [],
            sample_outline=sample_outline,
            learning_resources=learning_resources or []
        )
        
        self.db.add(prompt)
        self.db.commit()
        self.db.refresh(prompt)
        
        return prompt
