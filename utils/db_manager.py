
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
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        conn.commit()
        
    def save_article(self, article):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT OR REPLACE INTO articles (url, title, date, content, summary, ai_validation)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (
            article['url'],
            article['title'],
            article['date'],
            article.get('content', ''),
            article.get('summary', ''),
            article.get('ai_validation', '')
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
