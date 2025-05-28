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

def parse_date(date_str):
    """Parse a date string in various common formats."""
    formats = [
        "%Y-%m-%d",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%dT%H:%M:%S%z",
    ]
    for fmt in formats:
        try:
            return datetime.strptime(date_str, fmt)
        except Exception:
            continue
    try:
        # datetime.fromisoformat supports many ISO variants
        return datetime.fromisoformat(date_str.replace('Z', '+00:00'))
    except Exception:
        return None

def validate_timeframe(date_str, cutoff_date):
    """
    Validates if a date is within the specified timeframe
    """
    try:
        article_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        if isinstance(cutoff_date, datetime):
            cutoff = cutoff_date.date()
        else:
            cutoff = cutoff_date
        return article_date >= cutoff
    except Exception:
        return False
