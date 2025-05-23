import yaml
from datetime import datetime

def load_config():
    """
    Loads configuration from config.yaml
    """
    with open('config.yaml', 'r') as file:
        return yaml.safe_load(file)

def format_date(date_obj):
    """
    Formats datetime object to string
    """
    return date_obj.strftime('%Y-%m-%d')

def validate_timeframe(date_str, cutoff_date):
    """
    Validates if a date is within the specified timeframe
    """
    try:
        article_date = datetime.strptime(date_str, '%Y-%m-%d')
        return article_date >= cutoff_date
    except:
        return False
