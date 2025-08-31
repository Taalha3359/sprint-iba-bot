import os

# Bot token
BOT_TOKEN = os.getenv('BOT_TOKEN')

# Bot prefix
BOT_PREFIX = "!"

# Time limits for questions (in seconds)
TIME_LIMITS = {
    "math": 90,
    "english": 45, 
    "analytical": 60
}

# Scoring system
SCORING = {
    "correct": 1,
    "incorrect": -0.25
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
    "premium_channel_id": 1411595567934738432,
    "free_question_limit": 30,
    "admin_ids": [1344538585516478494]
}

