
import sqlite3

def init_db():
    conn = sqlite3.connect('telegram_bot.db')
    cursor = conn.cursor()

    # Users table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY
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
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        )
    ''')

    conn.commit()
    conn.close()

def add_user(user_id):
    conn = sqlite3.connect('telegram_bot.db')
    cursor = conn.cursor()
    cursor.execute('INSERT OR IGNORE INTO users (user_id) VALUES (?)', (user_id,))
    conn.commit()
    conn.close()

def add_quiz_question(user_id, quiz_name, question, correct_answer, wrong_answers):
    conn = sqlite3.connect('telegram_bot.db')
    cursor = conn.cursor()
    cursor.execute(
        'INSERT INTO quizzes (user_id, quiz_name, question, correct_answer, wrong_answers) VALUES (?, ?, ?, ?, ?)',
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
        'SELECT user_quiz_id, quiz_name, current_question_index, score, message_id, channel_id FROM user_quizzes WHERE user_id = ? ORDER BY user_quiz_id DESC LIMIT 1',
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
    cursor.execute('DELETE FROM user_quizzes WHERE user_quiz_id = ?', (user_quiz_id,))
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

def get_user_polls(user_id):
    conn = sqlite3.connect('telegram_bot.db')
    cursor = conn.cursor()
    cursor.execute('SELECT poll_id, question, channel_id, message_id, is_active FROM polls WHERE user_id = ?', (user_id,))
    polls = cursor.fetchall()
    conn.close()
    return polls

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

if __name__ == '__main__':
    init_db()
    print('Database initialized successfully.')
