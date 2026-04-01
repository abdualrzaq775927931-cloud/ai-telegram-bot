from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, DateTime, JSON, Float
from sqlalchemy.orm import relationship, declarative_base
from datetime import datetime

Base = declarative_base()

class User(Base):
    __tablename__ = 'users'
    
    id = Column(Integer, primary_key=True)
    telegram_id = Column(Integer, unique=True, index=True)
    username = Column(String, nullable=True)
    full_name = Column(String)
    xp = Column(Integer, default=0)
    level = Column(Integer, default=1)
    is_admin = Column(Boolean, default=False)
    # الميزة الجديدة: تم إضافة خاصية الحظر هنا
    is_banned = Column(Boolean, default=False) 
    created_at = Column(DateTime, default=datetime.utcnow)
    
    polls = relationship("Poll", back_populates="creator")
    quizzes = relationship("Quiz", back_populates="creator")
    responses = relationship("Response", back_populates="user")

class Poll(Base):
    __tablename__ = 'polls'
    
    id = Column(Integer, primary_key=True)
    creator_id = Column(Integer, ForeignKey('users.id'))
    question = Column(String)
    options = Column(JSON)  # قائمة الخيارات
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
    # هيكل الأسئلة: {question, options, correct_index, explanation}
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
    
