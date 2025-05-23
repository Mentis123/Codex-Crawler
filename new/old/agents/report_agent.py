import os
import logging
import json
from datetime import datetime
from io import BytesIO
from typing import List, Dict, Any, Optional

from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
import pandas as pd

from agents.base_agent import BaseAgent

# Configure logging
logger = logging.getLogger(__name__)

class ReportAgent(BaseAgent):
    """
    Agent responsible for generating reports from analyzed articles
    and selecting the most relevant articles
    """
    
    def __init__(self, config=None):
        """Initialize the report agent with configuration"""
        super().__init__(config)
        self.max_articles = config.get('max_report_articles', 10) if config else 10
        self.log_event("Report agent initialized")
    
    def process(self, input_data):
        """Process and rank articles, then generate reports"""
        if not input_data or not isinstance(input_data, list):
            self.log_event("No articles provided for reporting", "warning")
            return {
                "selected_articles": [],
                "pdf_report": None,
                "csv_report": None,
                "excel_report": None
            }
            
        articles = input_data
        self.log_event(f"Processing {len(articles)} articles for reporting")
        
        # Select and rank the best articles
        selected_articles = self.select_articles(articles)
        self.log_event(f"Selected {len(selected_articles)} articles for reports")
        
        # Generate reports in different formats
        try:
            pdf_data = self.generate_pdf_report(selected_articles)
            csv_data = self.generate_csv_report(selected_articles)
            excel_data = self.generate_excel_report(selected_articles)
            
            return {
                "selected_articles": selected_articles,
                "pdf_report": pdf_data,
                "csv_report": csv_data,
                "excel_report": excel_data
            }
        except Exception as e:
            self.log_event(f"Error generating reports: {str(e)}", "error")
            return {
                "selected_articles": selected_articles,
                "pdf_report": None,
                "csv_report": None,
                "excel_report": None
            }
    
    def select_articles(self, articles: List[Dict]) -> List[Dict]:
        """Select and rank the most relevant articles"""
        if not articles:
            return []
            
        # Sort articles by date (newest first)
        sorted_articles = sorted(
            articles,
            key=lambda x: datetime.strptime(x.get('date', '2000-01-01'), '%Y-%m-%d'),
            reverse=True
        )
        
        # Calculate relevance score for each article
        scored_articles = []
        for article in sorted_articles:
            score = self.calculate_relevance_score(article)
            scored_articles.append((score, article))
            
        # Sort by score (highest first)
        scored_articles.sort(reverse=True, key=lambda x: x[0])
        
        # Take top N articles
        selected = [article for _, article in scored_articles[:self.max_articles]]
        
        return selected
    
    def calculate_relevance_score(self, article: Dict) -> float:
        """Calculate a relevance score for an article based on various factors"""
        score = 0.0
        
        # AI Confidence score (0-100)
        ai_confidence = float(article.get('ai_confidence', 0))
        score += ai_confidence * 0.5  # Weight 50%
        
        # Recency factor (newer articles score higher)
        try:
            article_date = datetime.strptime(article.get('date', '2000-01-01'), '%Y-%m-%d')
            days_old = (datetime.now() - article_date).days
            recency_score = max(0, 100 - (days_old * 5))  # Lose 5 points per day old
            score += recency_score * 0.3  # Weight 30%
        except ValueError:
            # Date parsing failed
            score += 0  # No recency boost
            
        # Content quality (based on takeaway and key points)
        takeaway = article.get('takeaway', '')
        key_points = article.get('key_points', [])
        
        quality_score = 0
        if takeaway and len(takeaway) > 50:
            quality_score += 50
        if key_points and len(key_points) >= 3:
            quality_score += 50
            
        score += quality_score * 0.2  # Weight 20%
        
        return score
    
    def generate_pdf_report(self, articles: List[Dict]) -> Optional[bytes]:
        """Generate a PDF report for the selected articles"""
        if not articles:
            return None
            
        try:
            buffer = BytesIO()
            doc = SimpleDocTemplate(buffer, pagesize=letter)
            styles = getSampleStyleSheet()
            
            # Create custom styles
            title_style = styles['Heading1']
            subtitle_style = styles['Heading2']
            normal_style = styles['Normal']
            
            # Add custom paragraph style for article content
            article_style = ParagraphStyle(
                'ArticleStyle',
                parent=normal_style,
                spaceAfter=12,
                spaceBefore=6
            )
            
            # Add custom paragraph style for article takeaway
            takeaway_style = ParagraphStyle(
                'TakeawayStyle',
                parent=normal_style,
                leftIndent=20,
                rightIndent=20,
                spaceAfter=12,
                spaceBefore=12,
                borderWidth=1,
                borderColor=colors.lightgrey,
                borderPadding=10,
                borderRadius=5,
                backColor=colors.lightgrey
            )
            
            # Create the document content
            content = []
            
            # Add title
            today = datetime.now().strftime("%Y-%m-%d")
            content.append(Paragraph(f"AI News Report - {today}", title_style))
            content.append(Spacer(1, 12))
            content.append(Paragraph(f"Top {len(articles)} AI Articles", subtitle_style))
            content.append(Spacer(1, 24))
            
            # Add articles
            for i, article in enumerate(articles, 1):
                # Article title with link
                title = article.get('title', 'Untitled Article')
                url = article.get('url', '')
                
                content.append(Paragraph(f"{i}. <a href='{url}'>{title}</a>", subtitle_style))
                content.append(Spacer(1, 6))
                
                # Publication date and source
                date = article.get('date', 'Unknown date')
                source = article.get('source', 'Unknown source')
                content.append(Paragraph(f"Published: {date} | Source: {source}", normal_style))
                content.append(Spacer(1, 6))
                
                # Takeaway
                takeaway = article.get('takeaway', 'No takeaway available')
                content.append(Paragraph(f"<b>Key Takeaway:</b> {takeaway}", takeaway_style))
                
                # Key points
                key_points = article.get('key_points', [])
                if key_points:
                    content.append(Paragraph("<b>Key Points:</b>", article_style))
                    for point in key_points:
                        content.append(Paragraph(f"• {point}", article_style))
                
                # Add space between articles
                content.append(Spacer(1, 20))
            
            # Build the PDF
            doc.build(content)
            pdf_data = buffer.getvalue()
            buffer.close()
            
            return pdf_data
            
        except Exception as e:
            self.log_event(f"Error generating PDF: {str(e)}", "error")
            return None
    
    def generate_csv_report(self, articles: List[Dict]) -> Optional[bytes]:
        """Generate a CSV report for the selected articles"""
        if not articles:
            return None
            
        try:
            # Prepare data for CSV
            data = []
            for article in articles:
                # Extract key_points as string if it exists
                key_points = article.get('key_points', [])
                key_points_str = "; ".join(key_points) if key_points else ""
                
                row = {
                    'Title': article.get('title', ''),
                    'URL': article.get('url', ''),
                    'Date': article.get('date', ''),
                    'Source': article.get('source', ''),
                    'Takeaway': article.get('takeaway', ''),
                    'Key Points': key_points_str
                }
                data.append(row)
                
            # Create DataFrame and CSV
            df = pd.DataFrame(data)
            csv_buffer = BytesIO()
            df.to_csv(csv_buffer, index=False)
            
            return csv_buffer.getvalue()
            
        except Exception as e:
            self.log_event(f"Error generating CSV: {str(e)}", "error")
            return None
    
    def generate_excel_report(self, articles: List[Dict]) -> Optional[bytes]:
        """Generate an Excel report for the selected articles"""
        if not articles:
            return None
            
        try:
            # Prepare data for Excel
            data = []
            for article in articles:
                # Extract key_points as string if it exists
                key_points = article.get('key_points', [])
                key_points_str = "; ".join(key_points) if key_points else ""
                
                row = {
                    'Title': article.get('title', ''),
                    'URL': article.get('url', ''),
                    'Date': article.get('date', ''),
                    'Source': article.get('source', ''),
                    'Takeaway': article.get('takeaway', ''),
                    'Key Points': key_points_str
                }
                data.append(row)
                
            # Create DataFrame and Excel
            df = pd.DataFrame(data)
            excel_buffer = BytesIO()
            df.to_excel(excel_buffer, index=False, engine='openpyxl')
            
            return excel_buffer.getvalue()
            
        except Exception as e:
            self.log_event(f"Error generating Excel: {str(e)}", "error")
            return None