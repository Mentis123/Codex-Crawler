
import sqlite3
from datetime import datetime
import json

class DBManager:
    def __init__(self):
        self.conn = sqlite3.connect('articles.db')
        self.create_tables()
        
    def create_tables(self):
        cursor = self.conn.cursor()
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
        self.conn.commit()
        
    def save_article(self, article):
        cursor = self.conn.cursor()
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
        self.conn.commit()
        
    def get_articles(self, limit=None):
        cursor = self.conn.cursor()
        query = 'SELECT * FROM articles ORDER BY created_at DESC'
        if limit:
            query += f' LIMIT {limit}'
        cursor.execute(query)
        columns = [description[0] for description in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]
