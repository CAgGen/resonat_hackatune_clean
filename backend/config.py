"""Infrastructure · centralized config + tuning knobs.

Keep magic numbers out of logic and centralize them here; demo-time tuning happens in this one file.
"""
import os
import pathlib

from dotenv import load_dotenv

# .env lives at the repo root (one level above backend); specify it explicitly so cwd changes do not break loading.
load_dotenv(pathlib.Path(__file__).resolve().parents[1] / ".env")

# --- Cyanite ---
CYANITE_API_KEY = os.environ.get("CYANITE_API_KEY", "")
CYANITE_BASE_URL = "https://rest-api.cyanite.ai/v1"

# --- Jamendo ---
JAMENDO_CLIENT_ID = os.environ.get("JAMENDO_CLIENT_ID", "")
JAMENDO_BASE_URL = "https://api.jamendo.com/v3.0"

# --- OpenAI ---
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
OPENAI_BASE_URL = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1")
OPENAI_MODEL = os.environ.get("OPENAI_MODEL", "gpt-5.4-nano")
OPENAI_TIMEOUT = int(os.environ.get("OPENAI_TIMEOUT", "20"))

# --- Orchestration knobs ---
VISIBLE_N = 5        # Number of tracks shown in the recommendation list.
SEARCH_LIMIT = 20    # freeText recall limit.
SIMILAR_LIMIT = 10   # like/refill similarById recall limit.
PROFILE_REFILL_LIMIT = 10  # Semantic recall limit after anti-addiction dislikes, based on the user profile.
SOUNDS_LIKE_YOU_LIMIT = 5  # "Sounds like you" candidate count; dislikes flip through until exhausted.
EXPLAIN_SIMILAR_LIMIT = 50
EXPLAIN_TAG_MODELS = [
    "MainGenreV2",
    "MoodSimpleV2",
    "InstrumentsV2",
    "BpmV2",
    "VocalsV2",
    "AutoDescriptionV2",
]
