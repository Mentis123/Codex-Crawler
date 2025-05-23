import os
import logging
from datetime import datetime
import json
from openai import OpenAI
import traceback

# Configure logging
logger = logging.getLogger(__name__)

class BaseAgent:
    """
    Base class for all agents in the AI News Aggregation system
    Provides common functionality and standardized interfaces
    """
    
    def __init__(self, config=None):
        """Initialize the base agent with configuration settings"""
        self.config = config or {}
        self.start_time = datetime.now()
        self.api_client = None
        self.initialize_openai()
        
    def initialize_openai(self):
        """Initialize OpenAI client if API key is available"""
        try:
            api_key = os.getenv('OPENAI_API_KEY')
            if api_key:
                self.api_client = OpenAI(api_key=api_key)
                logger.info(f"{self.__class__.__name__} initialized OpenAI client")
            else:
                logger.warning(f"{self.__class__.__name__} could not initialize OpenAI client: Missing API key")
        except Exception as e:
            logger.error(f"{self.__class__.__name__} OpenAI initialization error: {str(e)}")
            
    def log_event(self, message, level="info"):
        """Standardized logging across all agents"""
        agent_name = self.__class__.__name__
        
        if level == "debug":
            logger.debug(f"[{agent_name}] {message}")
        elif level == "info":
            logger.info(f"[{agent_name}] {message}")
        elif level == "warning":
            logger.warning(f"[{agent_name}] {message}")
        elif level == "error":
            logger.error(f"[{agent_name}] {message}")
        elif level == "critical":
            logger.critical(f"[{agent_name}] {message}")
            
    def execute_ai_prompt(self, prompt, model="gpt-4o-mini", response_format="text", max_tokens=1500):
        """Execute an AI prompt with standardized error handling"""
        if not self.api_client:
            self.log_event("No OpenAI client available for prompt execution", "warning")
            return None
            
        try:
            # Set up response format
            format_config = None
            if response_format == "json_object":
                format_config = {"type": "json_object"}
            
            # Execute the API call
            response = self.api_client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                response_format=format_config,
                max_tokens=max_tokens
            )
            
            # Extract and process the response
            content = response.choices[0].message.content if response.choices else None
            
            if response_format == "json_object" and content:
                try:
                    return json.loads(content)
                except json.JSONDecodeError as e:
                    self.log_event(f"Failed to parse JSON response: {e}", "error")
                    return None
            
            return content
            
        except Exception as e:
            self.log_event(f"AI prompt execution error: {str(e)}", "error")
            self.log_event(traceback.format_exc(), "debug")
            return None
    
    def process(self, input_data):
        """
        Process abstract method that should be implemented by all agent classes
        """
        raise NotImplementedError("Agents must implement the process method")
        
    def report_status(self):
        """Report on agent processing status"""
        elapsed = datetime.now() - self.start_time
        seconds = elapsed.total_seconds()
        if seconds < 60:
            time_str = f"{seconds:.1f} seconds"
        else:
            minutes = seconds / 60
            time_str = f"{minutes:.1f} minutes"
            
        return {
            "agent": self.__class__.__name__,
            "elapsed_time": time_str,
            "status": "Active"
        }