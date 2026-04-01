from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, DateTime, JSON, Float, BigInteger
from sqlalchemy.orm import relationship, declarative_base
from datetime import datetime

Base = declarative_base()

class User(Base):
    __tablename__ = 'users'
    
    id = Column(Integer, primary_key=True)
    telegram_id = Column(BigInteger, unique=True, index=True)
    username = Column(String, nullable=True)
    full_name = Column(String)
    xp = Column(Integer, default=0)
    level = Column(Integer, default=1)
    is_admin = Column(Boolean, default=False)
    is_banned = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    polls = relationship("Poll", back_populates="creator")
    quizzes = relationship("Quiz", back_populates="creator")
    responses = relationship("Response", back_populates="user")

# --- الجدول الجديد للتحكم في إعدادات البوت من التليجرام ---
class BotSettings(Base):
    __tablename__ = 'bot_settings'
    id = Column(Integer, primary_key=True)
    key = Column(String, unique=True, index=True) # مفاتيح مثل 'force_sub'
    value = Column(String, nullable=True)         # يوزر القناة مثلاً @MyChannel

class Channel(Base):
    __tablename__ = 'channels'
    
    id = Column(Integer, primary_key=True)
    channel_id = Column(BigInteger, unique=True, index=True)
    title = Column(String)
    added_by = Column(Integer, ForeignKey('users.id'))
    post_interval = Column(Integer, default=120)
    is_active = Column(Boolean, default=True)
    last_post_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

class GroupConfig(Base):
    __tablename__ = 'group_configs'
    id = Column(Integer, primary_key=True)
    group_id = Column(BigInteger, unique=True)
    group_title = Column(String)
    is_active = Column(Boolean, default=True)

class Poll(Base):
    __tablename__ = 'polls'
    id = Column(Integer, primary_key=True)
    creator_id = Column(Integer, ForeignKey('users.id'))
    question = Column(String)
    options = Column(JSON)
    is_anonymous = Column(Boolean, default=True)
    is_closed = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    creator = relationship("User", back_populates="polls")

class Quiz(Base):
    __tablename__ = 'quizzes'
    id = Column(Integer, primary_key=True)
    creator_id = Column(Integer, ForeignKey('users.id'))
    title = Column(String)
    description = Column(String, nullable=True)
    questions = Column(JSON)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    creator = relationship("User", back_populates="quizzes")
    results = relationship("QuizResult", back_populates="quiz")

class QuizResult(Base):
    __tablename__ = 'quiz_results'
    id = Column(Integer, primary_key=True)
    quiz_id = Column(Integer, ForeignKey('quizzes.id'))
    user_id = Column(Integer, ForeignKey('users.id'))
    score = Column(Integer)
    total_questions = Column(Integer)
    completed_at = Column(DateTime, default=datetime.utcnow)
    quiz = relationship("Quiz", back_populates="results")
    user = relationship("User")

class Response(Base):
    __tablename__ = 'responses'
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'))
    poll_id = Column(Integer, ForeignKey('polls.id'))
    option_index = Column(Integer)
    created_at = Column(DateTime, default=datetime.utcnow)
    user = relationship("User", back_populates="responses")
    
