from .db_manager import get_session
from .models import User, Poll, Quiz, QuizResult
from datetime import datetime

class UserManager:
    @staticmethod
    def get_or_create_user(telegram_id, username=None, full_name=None):
        session = get_session()
        user = session.query(User).filter_by(telegram_id=telegram_id).first()
        if not user:
            user = User(
                telegram_id=telegram_id,
                username=username,
                full_name=full_name or "Unknown"
            )
            session.add(user)
            session.commit()
            session.refresh(user)
        return user

    @staticmethod
    def add_xp(telegram_id, amount):
        session = get_session()
        user = session.query(User).filter_by(telegram_id=telegram_id).first()
        if user:
            user.xp += amount
            # Simple level calculation: Level = (XP // 100) + 1
            new_level = (user.xp // 100) + 1
            if new_level > user.level:
                user.level = new_level
            session.commit()
            return user
        return None

    @staticmethod
    def get_leaderboard(limit=10):
        session = get_session()
        return session.query(User).order_by(User.xp.desc()).limit(limit).all()

    @staticmethod
    def get_user_stats(telegram_id):
        session = get_session()
        user = session.query(User).filter_by(telegram_id=telegram_id).first()
        if user:
            total_quizzes = session.query(QuizResult).filter_by(user_id=user.id).count()
            avg_score = session.query(QuizResult.score).filter_by(user_id=user.id).all()
            return {
                "xp": user.xp,
                "level": user.level,
                "total_quizzes": total_quizzes,
                "avg_score": sum([s[0] for s in avg_score]) / len(avg_score) if avg_score else 0
            }
        return None
