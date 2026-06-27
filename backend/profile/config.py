"""Config for the user-profile / memory module. Reads the repo-root .env."""
import os
from dotenv import load_dotenv

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.abspath(os.path.join(_HERE, "..", ".."))

load_dotenv(os.path.join(_HERE, ".env"))      # optional local override
load_dotenv(os.path.join(_REPO, ".env"))      # repo-root .env (Cyanite key)

CYANITE_API_KEY = os.environ.get("CYANITE_API_KEY", "").strip()
CYANITE_BASE_URL = os.environ.get("CYANITE_BASE_URL", "https://rest-api.cyanite.ai/v1").strip()

DATA_DIR = os.environ.get("DATA_DIR", os.path.join(_REPO, "data"))
CACHE_DIR = os.environ.get("CACHE_DIR", os.path.join(_HERE, ".cache"))
DB_PATH = os.environ.get("MEMORY_DB", os.path.join(_HERE, "memory.db"))

# Optional LLM for natural-language memory summaries / aggregation polish.
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "").strip()
LLM_MODEL = os.environ.get("LLM_MODEL", "claude-sonnet-4-6").strip()

# Aalto OpenAI API gateway (Azure APIM). Responses API only.
AALTO_OPENAI_API_KEY = os.environ.get("AALTO_OPENAI_API_KEY", "").strip()
AALTO_BASE_URL = os.environ.get("AALTO_BASE_URL", "https://aalto-openai-apigw.azure-api.net").strip()
AALTO_MODEL = os.environ.get("AALTO_MODEL", "gpt-5-mini-2025-08-07").strip()

MOCK = not bool(CYANITE_API_KEY)

# Models we need to build a taste profile (one tagging call returns all of them).
PROFILE_MODELS = [
    "MainGenreV2", "MoodSimpleV2", "InstrumentsV2", "CharacterV2", "MovementV2",
    "BpmV2", "TempoV1", "ValenceArousalV2", "MusicalEraV2", "VocalsV2",
    "AutoDescriptionV2",
]
