
import sqlite3
from datetime import datetime
import json
import threading

class DBManager:
    def __init__(self):
        self.db_path = 'articles.db'
        self.local = threading.local()
        self.create_tables()
        
    def get_connection(self):
        """Get a thread-local database connection"""
        if not hasattr(self.local, 'conn'):
            self.local.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        return self.local.conn
        
    def create_tables(self):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS articles (
                url TEXT PRIMARY KEY,
                title TEXT,
                date TEXT,
                content TEXT,
                summary TEXT,
                ai_validation TEXT,
                category TEXT,
                category_justification TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        self._add_column_if_not_exists('articles', 'category', 'TEXT')
        self._add_column_if_not_exists('articles', 'category_justification', 'TEXT')
        conn.commit()

    def _add_column_if_not_exists(self, table_name, column_name, column_type):
        cursor = self.get_connection().cursor()
        cursor.execute(f"PRAGMA table_info({table_name})")
        columns = [info[1] for info in cursor.fetchall()]
        if column_name not in columns:
            try:
                cursor.execute(
                    f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type}"
                )
                self.get_connection().commit()
            except Exception:
                pass
        
    def save_article(self, article):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT OR REPLACE INTO articles (
                url, title, date, content, summary, ai_validation,
                category, category_justification
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            article['url'],
            article['title'],
            article['date'],
            article.get('content', ''),
            article.get('summary', ''),
            article.get('ai_validation', ''),
            article.get('category'),
            article.get('category_justification')
        ))
        conn.commit()
        
    def get_articles(self, limit=None):
        conn = self.get_connection()
        cursor = conn.cursor()
        query = 'SELECT * FROM articles ORDER BY created_at DESC'
        if limit:
            query += f' LIMIT {limit}'
        cursor.execute(query)
        columns = [description[0] for description in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]
