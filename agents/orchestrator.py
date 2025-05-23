import os
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
import time
import json

from agents.base_agent import BaseAgent
from agents.crawler_agent import CrawlerAgent
from agents.analyzer_agent import AnalyzerAgent
from agents.report_agent import ReportAgent
from agents.evaluation_agent import EvaluationAgent

# Configure logging
logger = logging.getLogger(__name__)

class Orchestrator:
    """
    Coordinates the workflow between different agents in the news aggregation system
    """
    
    def __init__(self, config=None):
        """Initialize the orchestrator with configuration settings"""
        self.config = config or {}
        self.start_time = datetime.now()
        
        # Initialize agent instances
        self.crawler = CrawlerAgent(self.config.get('crawler_config', {}))
        self.analyzer = AnalyzerAgent(self.config.get('analyzer_config', {}))
        self.evaluator = EvaluationAgent(self.config.get('evaluation_config', {}))
        self.reporter = ReportAgent(self.config.get('report_config', {}))
        
        # Processing state
        self.articles = []
        self.analyzed_articles = []
        self.reports = {}
        self.status_messages = []
        self.is_processing = False
        
        logger.info("Orchestrator initialized with all agents ready")
    
    def update_status(self, message):
        """Update processing status with timestamp"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        status_msg = f"[{timestamp}] {message}"
        self.status_messages.insert(0, status_msg)
        logger.info(f"Status: {message}")
        
    def run_workflow(self, source_urls, time_period=7, time_unit="Days"):
        """
        Run the complete news aggregation workflow with all agents
        
        Args:
            source_urls: List of source URLs to search for articles
            time_period: Number of time units to look back
            time_unit: "Days" or "Weeks"
            
        Returns:
            Dict containing workflow results
        """
        self.is_processing = True
        self.start_time = datetime.now()
        self.status_messages = []
        self.update_status(f"Starting news aggregation workflow with {len(source_urls)} sources")
        
        try:
            # Calculate cutoff time
            days_to_subtract = time_period * 7 if time_unit == "Weeks" else time_period
            cutoff_time = datetime.now() - timedelta(days=days_to_subtract)
            self.update_status(f"Time period: {time_period} {time_unit}, Cutoff: {cutoff_time}")
            
            # Step 1: Crawl sources for articles
            self.update_status("Crawling sources for AI articles...")
            crawler_result = self.crawler.process(source_urls, cutoff_time)
            
            if not crawler_result or len(crawler_result) == 0:
                self.update_status("No articles found. Workflow complete.")
                self.is_processing = False
                return {
                    "success": True,
                    "articles": [],
                    "reports": {},
                    "status": self.status_messages,
                    "execution_time": self._get_execution_time()
                }
                
            self.articles = crawler_result
            self.update_status(f"Found {len(self.articles)} potential articles")
            
            # Step 2: Analyze and validate articles
            self.update_status("Analyzing article content...")
            
            # First, fetch full content for any articles that don't have it
            for article in self.articles:
                if not article.get('content'):
                    self.update_status(f"Fetching content for: {article['title']}")
                    article['content'] = self.crawler.extract_full_content(article['url'])
            
            filtered_articles = [a for a in self.articles if a.get('content')]
            self.update_status(f"Analyzing {len(filtered_articles)} articles with content")
            
            self.analyzed_articles = self.analyzer.process(filtered_articles)
            self.update_status(f"Successfully analyzed {len(self.analyzed_articles)} articles")

            # Step 2b: Evaluate against selection criteria
            self.update_status("Evaluating articles against criteria...")
            self.analyzed_articles = self.evaluator.evaluate(self.analyzed_articles)
            
            # Step 3: Generate reports
            self.update_status("Generating reports...")
            report_result = self.reporter.process(self.analyzed_articles)
            
            self.reports = report_result
            selected_count = len(report_result.get('selected_articles', []))
            self.update_status(f"Generated reports with {selected_count} selected articles")
            
            # Complete workflow
            self.is_processing = False
            execution_time = self._get_execution_time()
            self.update_status(f"Workflow complete in {execution_time}")
            
            return {
                "success": True,
                "articles": self.analyzed_articles,
                "selected_articles": report_result.get('selected_articles', []),
                "reports": {
                    "pdf": report_result.get('pdf_report'),
                    "csv": report_result.get('csv_report'),
                    "excel": report_result.get('excel_report')
                },
                "status": self.status_messages,
                "execution_time": execution_time
            }
            
        except Exception as e:
            logger.error(f"Error in workflow: {str(e)}")
            self.update_status(f"Error: {str(e)}")
            self.is_processing = False
            return {
                "success": False,
                "error": str(e),
                "status": self.status_messages,
                "execution_time": self._get_execution_time()
            }
    
    def _get_execution_time(self):
        """Calculate execution time as a formatted string"""
        elapsed = datetime.now() - self.start_time
        seconds = elapsed.total_seconds()
        
        if seconds < 60:
            return f"{seconds:.1f} seconds"
        else:
            minutes = int(seconds // 60)
            remaining_seconds = int(seconds % 60)
            return f"{minutes}m {remaining_seconds}s"
            
    def get_status(self):
        """Get current status information"""
        return {
            "is_processing": self.is_processing,
            "articles_found": len(self.articles),
            "articles_analyzed": len(self.analyzed_articles),
            "reports_generated": bool(self.reports),
            "execution_time": self._get_execution_time(),
            "status_messages": self.status_messages
        }
        
    def load_sources(self, file_path=None, test_mode=False):
        """Load source websites from configuration or file"""
        if test_mode:
            # Return test sources only
            return ['https://www.wired.com/tag/artificial-intelligence/']
            
        try:
            if file_path and os.path.exists(file_path):
                with open(file_path, 'r') as f:
                    sources = [line.strip() for line in f if line.strip()]
                logger.info(f"Loaded {len(sources)} sources from {file_path}")
                return sources
            elif 'sources' in self.config:
                sources = self.config['sources']
                logger.info(f"Loaded {len(sources)} sources from config")
                return sources
            else:
                # Default sources if none provided
                logger.warning("No source configuration found, using defaults")
                return [
                    'https://www.wired.com/tag/artificial-intelligence/',
                    'https://techcrunch.com/category/artificial-intelligence/',
                    'https://venturebeat.com/category/ai/'
                ]
        except Exception as e:
            logger.error(f"Error loading sources: {str(e)}")
            return []