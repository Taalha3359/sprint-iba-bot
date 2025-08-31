import os
from datetime import timedelta

# Bot token will be loaded from environment variable with fallback for testing
BOT_TOKEN = os.getenv('BOT_TOKEN', 'dummy_token_for_testing')  # Fallback for testing

# MongoDB connection string
MONGO_URI = os.getenv('MONGO_URI', 'mongodb://localhost:27017')

# Database name
DATABASE_NAME = os.getenv('DATABASE_NAME', 'discord_bot')

# Bot prefix for commands
BOT_PREFIX = "!"

# Time limits for questions (in seconds)
TIME_LIMITS = {
    "math": 90,
    "english": 45, 
    "analytical": 60,
    "puzzle": 300
}

# Mock test settings
MOCK_TEST_CONFIG = {
    "math_count": 25,
    "english_count": 30,
    "analytical_count": 15,
    "time_limit": 3600
}

# Scoring system
SCORING = {
    "correct": 1,
    "incorrect": -0.25
}

# Image folder paths
IMAGE_PATHS = {
    "math": "./images/math/",
    "english": "./images/english/", 
    "analytical": "./images/analytical/"
}

# Math topics
MATH_TOPICS = [
    "age", "average", "fraction", "interest", "Number",
    "permutation", "profit-loss", "ratio", "solids", "triangle",
    "angle", "circle", "inequality", "mixture", "percentage",
    "probability", "quadrilateral", "set", "speed", "workdone"
]

# English topics
ENGLISH_TOPICS = [
    "analogy", "correct-use-of-word", "error-detection",
    "reading-comprehension", "rearrange", "sentence-completion",
    "sentence-correction", "suffix-prefix", "syn-ant"
]

# Analytical topics
ANALYTICAL_TOPICS = [
    "cr", "ds", "puzzle"
]

# Premium access settings
PREMIUM_SETTINGS = {
    "premium_channel_id": 1411595567934738432,  # Replace with your premium channel ID
    "free_question_limit": 30,
    "admin_ids": [1344538585516478494],  # Replace with admin user IDs
    "ticket_durations": {
        "7days": 7,
        "14days": 14, 
        "1month": 30,
        "3months": 90
    },
    "premium_roles": ["Premium", "VIP"]  # Discord role names that grant premium access
}

# Database settings
DATABASE_SETTINGS = {
    "connection_timeout": 30000,  # 30 seconds
    "server_selection_timeout": 30000,  # 30 seconds
    "max_pool_size": 100,
    "min_pool_size": 10,
    "max_idle_time_ms": 60000,  # 1 minute
    "socket_timeout_ms": 30000,  # 30 seconds
    "connect_timeout_ms": 30000,  # 30 seconds
    "wait_queue_timeout_ms": 30000,  # 30 seconds
    "heartbeat_frequency_ms": 10000,  # 10 seconds
    "retry_writes": True,
    "retry_reads": True
}

# Cache settings for improved performance
CACHE_SETTINGS = {
    "user_cache_ttl": 300,  # 5 minutes in seconds
    "question_cache_ttl": 3600,  # 1 hour in seconds
    "max_cached_users": 1000,
    "max_cached_questions": 500,
    "leaderboard_cache_ttl": 60  # 1 minute in seconds
}

# Rate limiting settings
RATE_LIMIT_SETTINGS = {
    "max_questions_per_minute": 10,
    "max_commands_per_minute": 20,
    "cooldown_period": 5,  # seconds
    "premium_cooldown_multiplier": 0.5  # Premium users get 50% shorter cooldown
}

# Logging settings
LOGGING_SETTINGS = {
    "level": "INFO",  # DEBUG, INFO, WARNING, ERROR, CRITICAL
    "file_path": "./logs/bot.log",
    "max_file_size": 10485760,  # 10MB
    "backup_count": 5,
    "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    "date_format": "%Y-%m-%d %H:%M:%S"
}

# Performance optimization settings
PERFORMANCE_SETTINGS = {
    "batch_update_size": 50,  # Number of operations to batch together
    "background_task_interval": 300,  # 5 minutes in seconds
    "cleanup_interval": 86400,  # 24 hours in seconds
    "connection_pool_monitoring": True,
    "query_timeout": 30,  # seconds
    "max_concurrent_operations": 100
}

# Feature flags
FEATURE_FLAGS = {
    "enable_leaderboard": True,
    "enable_premium_features": True,
    "enable_analytics": True,
    "enable_background_tasks": True,
    "enable_caching": True,
    "enable_rate_limiting": True,
    "enable_config_validation": False  # Disable validation during testing
}

# Analytics settings
ANALYTICS_SETTINGS = {
    "track_question_usage": True,
    "track_user_behavior": True,
    "track_performance_metrics": True,
    "retention_days": 30,  # How long to keep analytics data
    "anonymize_data": True  # Whether to anonymize user data for analytics
}

# Backup settings
BACKUP_SETTINGS = {
    "enable_auto_backup": True,
    "backup_interval": 86400,  # 24 hours in seconds
    "retain_backups": 7,  # Number of backups to keep
    "backup_path": "./backups"
}

# Notification settings
NOTIFICATION_SETTINGS = {
    "notify_on_error": True,
    "error_channel_id": None,  # Discord channel ID for error notifications
    "notify_on_backup": True,
    "backup_channel_id": None,  # Discord channel ID for backup notifications
    "notify_on_maintenance": True,
    "maintenance_channel_id": None  # Discord channel ID for maintenance notifications
}

# Maintenance settings
MAINTENANCE_SETTINGS = {
    "scheduled_maintenance_window": {
        "enabled": False,
        "start_time": "02:00",  # 2 AM
        "end_time": "04:00",    # 4 AM
        "timezone": "UTC"
    },
    "maintenance_message": "The bot is currently undergoing maintenance. Please try again later."
}

# Embed color settings
EMBED_COLORS = {
    "success": 0x00FF00,  # Green
    "error": 0xFF0000,    # Red
    "warning": 0xFFA500,  # Orange
    "info": 0x0099FF,     # Blue
    "premium": 0xFFD700,  # Gold
    "admin": 0x800080     # Purple
}

# Localization settings (for future multi-language support)
LOCALIZATION_SETTINGS = {
    "default_language": "en",
    "supported_languages": ["en"],
    "fallback_to_english": True
}

# API settings (for future external integrations)
API_SETTINGS = {
    "timeout": 30,
    "max_retries": 3,
    "retry_delay": 1,
    "enable_metrics": True
}

# Security settings
SECURITY_SETTINGS = {
    "max_message_size": 2000,  # characters
    "sanitize_input": True,
    "prevent_mention_spam": True,
    "max_mentions_per_message": 5,
    "blocked_words": [],  # List of words to block
    "allowed_domains": []  # List of allowed domains for links
}

# Validation function to check config values
def validate_config():
    """Validate configuration values"""
    # Skip validation if disabled in feature flags
    if not FEATURE_FLAGS.get("enable_config_validation", True):
        return []
    
    errors = []
    
    # Check required environment variables only in production
    # Allow dummy token for testing scenarios
    if not BOT_TOKEN or BOT_TOKEN == 'dummy_token_for_testing':
        # Only error if we're not in a testing scenario
        if not os.getenv('TESTING', False) and not os.getenv('GITHUB_ACTIONS', False):
            errors.append("BOT_TOKEN environment variable is required")
    
    # Check premium settings
    if PREMIUM_SETTINGS["free_question_limit"] < 0:
        errors.append("free_question_limit must be a positive number")
    
    # Check time limits
    for subject, limit in TIME_LIMITS.items():
        if limit <= 0:
            errors.append(f"Time limit for {subject} must be positive")
    
    # Check scoring
    if SCORING["correct"] <= 0:
        errors.append("Correct answer score must be positive")
    
    return errors

# Helper function to get premium duration
def get_premium_duration(duration_key):
    """Get timedelta for premium duration"""
    durations = {
        "7days": timedelta(days=7),
        "14days": timedelta(days=14),
        "1month": timedelta(days=30),
        "3months": timedelta(days=90)
    }
    return durations.get(duration_key, timedelta(days=7))

# Helper function to check if user is admin
def is_admin(user_id):
    """Check if user ID is in admin list"""
    return user_id in PREMIUM_SETTINGS["admin_ids"]

# Helper function to get embed color
def get_embed_color(color_type):
    """Get hex color for embed by type"""
    return EMBED_COLORS.get(color_type, 0x0099FF)  # Default to blue

# Check if we're running in a testing environment
def is_testing_environment():
    """Check if we're running in a test environment"""
    return os.getenv('TESTING', False) or os.getenv('GITHUB_ACTIONS', False) or BOT_TOKEN == 'dummy_token_for_testing'

# Validate config on import, but skip in testing environments
config_errors = []
if not is_testing_environment():
    config_errors = validate_config()
    if config_errors:
        print("Configuration errors detected:")
        for error in config_errors:
            print(f"  - {error}")
        print("Please fix these errors before running the bot.")
else:
    print("Running in testing environment - configuration validation skipped")
