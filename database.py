
import sqlite3
import json

def init_db():
    conn = sqlite3.connect('telegram_bot.db')
    cursor = conn.cursor()

    # Users table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            full_name TEXT,
            total_score INTEGER DEFAULT 0,
            is_blocked BOOLEAN DEFAULT FALSE,
            joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Polls table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS polls (
            poll_id TEXT PRIMARY KEY,
            user_id INTEGER,
            question TEXT,
            options TEXT, -- JSON string of options
            channel_id INTEGER,
            message_id INTEGER,
            is_active BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        )
    ''')

    # Quizzes table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS quizzes (
            quiz_name TEXT,
            user_id INTEGER,
            question TEXT,
            correct_answer TEXT,
            wrong_answers TEXT, -- JSON string of wrong answers
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (quiz_name, user_id, question),
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        )
    ''')

    # User quizzes (to track which quizzes a user has started)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_quizzes (
            user_quiz_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            quiz_name TEXT,
            current_question_index INTEGER DEFAULT 0,
            score INTEGER DEFAULT 0,
            message_id INTEGER, -- Message ID of the current quiz question
            channel_id INTEGER, -- If quiz is published in a channel/group
            is_finished BOOLEAN DEFAULT FALSE,
            started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        )
    ''')

    conn.commit()
    conn.close()

def add_user(user_id, username=None, full_name=None):
    conn = sqlite3.connect('telegram_bot.db')
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO users (user_id, username, full_name) 
        VALUES (?, ?, ?)
        ON CONFLICT(user_id) DO UPDATE SET 
            username = excluded.username,
            full_name = excluded.full_name
    ''', (user_id, username, full_name))
    conn.commit()
    conn.close()

def get_all_users():
    conn = sqlite3.connect('telegram_bot.db')
    cursor = conn.cursor()
    cursor.execute('SELECT user_id FROM users WHERE is_blocked = FALSE')
    users = [row[0] for row in cursor.fetchall()]
    conn.close()
    return users

def get_stats():
    conn = sqlite3.connect('telegram_bot.db')
    cursor = conn.cursor()
    
    cursor.execute('SELECT COUNT(*) FROM users')
    total_users = cursor.fetchone()[0]
    
    cursor.execute('SELECT COUNT(*) FROM polls')
    total_polls = cursor.fetchone()[0]
    
    cursor.execute('SELECT COUNT(DISTINCT quiz_name) FROM quizzes')
    total_quizzes = cursor.fetchone()[0]
    
    conn.close()
    return {
        "users": total_users,
        "polls": total_polls,
        "quizzes": total_quizzes
    }

def update_user_score(user_id, points):
    conn = sqlite3.connect('telegram_bot.db')
    cursor = conn.cursor()
    cursor.execute('UPDATE users SET total_score = total_score + ? WHERE user_id = ?', (points, user_id))
    conn.commit()
    conn.close()

def get_leaderboard(limit=10):
    conn = sqlite3.connect('telegram_bot.db')
    cursor = conn.cursor()
    cursor.execute('''
        SELECT full_name, username, total_score 
        FROM users 
        WHERE total_score > 0 
        ORDER BY total_score DESC 
        LIMIT ?
    ''', (limit,))
    leaderboard = cursor.fetchall()
    conn.close()
    return leaderboard

def add_quiz_question(user_id, quiz_name, question, correct_answer, wrong_answers):
    conn = sqlite3.connect('telegram_bot.db')
    cursor = conn.cursor()
    cursor.execute(
        'INSERT OR REPLACE INTO quizzes (user_id, quiz_name, question, correct_answer, wrong_answers) VALUES (?, ?, ?, ?, ?)',
        (user_id, quiz_name, question, correct_answer, wrong_answers)
    )
    conn.commit()
    conn.close()

def get_user_quizzes(user_id):
    conn = sqlite3.connect('telegram_bot.db')
    cursor = conn.cursor()
    cursor.execute('SELECT DISTINCT quiz_name FROM quizzes WHERE user_id = ?', (user_id,))
    quizzes = [row[0] for row in cursor.fetchall()]
    conn.close()
    return quizzes

def delete_quiz(user_id, quiz_name):
    conn = sqlite3.connect('telegram_bot.db')
    cursor = conn.cursor()
    cursor.execute('DELETE FROM quizzes WHERE user_id = ? AND quiz_name = ?', (user_id, quiz_name))
    conn.commit()
    conn.close()

def delete_all_quizzes(user_id):
    conn = sqlite3.connect('telegram_bot.db')
    cursor = conn.cursor()
    cursor.execute('DELETE FROM quizzes WHERE user_id = ?', (user_id,))
    conn.commit()
    conn.close()

def get_quiz_questions(user_id, quiz_name):
    conn = sqlite3.connect('telegram_bot.db')
    cursor = conn.cursor()
    cursor.execute(
        'SELECT question, correct_answer, wrong_answers FROM quizzes WHERE user_id = ? AND quiz_name = ?',
        (user_id, quiz_name)
    )
    questions = cursor.fetchall()
    conn.close()
    return questions

def start_user_quiz(user_id, quiz_name, message_id=None, channel_id=None):
    conn = sqlite3.connect('telegram_bot.db')
    cursor = conn.cursor()
    cursor.execute(
        'INSERT INTO user_quizzes (user_id, quiz_name, message_id, channel_id) VALUES (?, ?, ?, ?)',
        (user_id, quiz_name, message_id, channel_id)
    )
    conn.commit()
    conn.close()

def get_user_current_quiz_state(user_id):
    conn = sqlite3.connect('telegram_bot.db')
    cursor = conn.cursor()
    cursor.execute(
        'SELECT user_quiz_id, quiz_name, current_question_index, score, message_id, channel_id FROM user_quizzes WHERE user_id = ? AND is_finished = FALSE ORDER BY user_quiz_id DESC LIMIT 1',
        (user_id,)
    )
    state = cursor.fetchone()
    conn.close()
    return state

def update_user_quiz_state(user_quiz_id, current_question_index, score, message_id=None):
    conn = sqlite3.connect('telegram_bot.db')
    cursor = conn.cursor()
    if message_id:
        cursor.execute(
            'UPDATE user_quizzes SET current_question_index = ?, score = ?, message_id = ? WHERE user_quiz_id = ?',
            (current_question_index, score, message_id, user_quiz_id)
        )
    else:
        cursor.execute(
            'UPDATE user_quizzes SET current_question_index = ?, score = ? WHERE user_quiz_id = ?',
            (current_question_index, score, user_quiz_id)
        )
    conn.commit()
    conn.close()

def end_user_quiz(user_quiz_id):
    conn = sqlite3.connect('telegram_bot.db')
    cursor = conn.cursor()
    cursor.execute('UPDATE user_quizzes SET is_finished = TRUE WHERE user_quiz_id = ?', (user_quiz_id,))
    conn.commit()
    conn.close()

def add_poll(poll_id, user_id, question, options, channel_id, message_id):
    conn = sqlite3.connect('telegram_bot.db')
    cursor = conn.cursor()
    cursor.execute(
        'INSERT INTO polls (poll_id, user_id, question, options, channel_id, message_id) VALUES (?, ?, ?, ?, ?, ?)',
        (poll_id, user_id, question, options, channel_id, message_id)
    )
    conn.commit()
    conn.close()

def get_poll_by_message_id(message_id, channel_id):
    conn = sqlite3.connect('telegram_bot.db')
    cursor = conn.cursor()
    cursor.execute('SELECT poll_id, user_id, question, options, is_active FROM polls WHERE message_id = ? AND channel_id = ?', (message_id, channel_id))
    poll = cursor.fetchone()
    conn.close()
    return poll

def deactivate_poll(poll_id):
    conn = sqlite3.connect('telegram_bot.db')
    cursor = conn.cursor()
    cursor.execute('UPDATE polls SET is_active = FALSE WHERE poll_id = ?', (poll_id,))
    conn.commit()
    conn.close()
