from .db_manager import get_session
from .models import User, Poll, Quiz, QuizResult
from datetime import datetime

class UserManager:
    @staticmethod
    def get_or_create_user(telegram_id, username=None, full_name=None):
        session = get_session()
        user = session.query(User).filter_by(telegram_id=telegram_id).first()
        created = False
        if not user:
            user = User(
                telegram_id=telegram_id,
                username=username,
                full_name=full_name or "Unknown"
            )
            session.add(user)
            session.commit()
            session.refresh(user)
            created = True
        return user, created

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
            results = session.query(QuizResult).filter_by(user_id=user.id).all()
            total_quizzes = len(results)
            avg_score = sum([r.score for r in results]) / total_quizzes if total_quizzes > 0 else 0
            return {
                "xp": user.xp,
                "level": user.level,
                "total_quizzes": total_quizzes,
                "avg_score": avg_score
            }
        return None
