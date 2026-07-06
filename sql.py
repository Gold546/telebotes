import sqlite3

DB_NAME = 'users.db'


def init_db():
    """Создает таблицы, если их еще нет"""
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute("PRAGMA foreign_keys = ON")

        # Таблица пользователей (главный тут Telegram ID)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                telegram_id INTEGER PRIMARY KEY,
                username TEXT
            )
        ''')

        # Таблица снов (привязана к telegram_id)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS data_sleep (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                dream TEXT,
                emotions TEXT,
                raiting TEXT,  
                FOREIGN KEY (user_id) REFERENCES users (telegram_id) ON DELETE CASCADE
            )
        ''')
        conn.commit()


def save_user(user_id: int, username: str):
    """Сохраняет пользователя в базу. Если уже есть — обновляет username"""
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO users (telegram_id, username) 
            VALUES (?, ?)
            ON CONFLICT(telegram_id) DO UPDATE SET username = excluded.username
        ''', (user_id, username))
        conn.commit()


def save_dream(user_id: int, dream: str, emotions: str, raiting: str):
    """Сохраняет записанный сон, эмоции и оценку пользователя"""
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO data_sleep (user_id, dream, emotions, raiting) 
            VALUES (?, ?, ?, ?)
        ''', (user_id, dream, emotions, raiting))
        conn.commit()