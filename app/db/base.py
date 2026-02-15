from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

# Import all models here for Alembic to detect them
from app.models.user import User, RefreshToken
from app.models.plan import UserPlan, DailyActivity, CycleCompletion
from app.models.speaking import SpeakingExercise, SpeakingSubmission
from app.models.vocabulary import VocabularyWord, UserVocabulary, VocabularyPracticeSession
from app.models.writing import WritingPrompt, WritingSubmission
from app.models.achievement import Achievement, UserAchievement
from app.models.progress import DailyProgress
from app.models.analytics import AnalyticsEvent
