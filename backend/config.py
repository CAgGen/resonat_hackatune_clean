"""基础设施 · 集中配置 + 可调旋钮。

逻辑里不写魔法数字，全集中到这里——演示现场要调就调这一个文件。
"""
import os
import pathlib

from dotenv import load_dotenv

# .env 在仓库根（backend 的上一级），显式指定，避免 cwd 不同导致读不到
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

# --- 编排旋钮 ---
VISIBLE_N = 5        # 推荐列表一次展示几首
SEARCH_LIMIT = 20    # freeText 召回上限
SIMILAR_LIMIT = 10   # like/refill similarById 召回上限
PROFILE_REFILL_LIMIT = 10  # 防沉迷 dislike 后按用户画像语义召回上限
SOUNDS_LIKE_YOU_LIMIT = 5  # 「听起来像你」候选数，不喜欢逐张翻到耗尽
EXPLAIN_SIMILAR_LIMIT = 50
EXPLAIN_TAG_MODELS = [
    "MainGenreV2",
    "MoodSimpleV2",
    "InstrumentsV2",
    "BpmV2",
    "VocalsV2",
    "AutoDescriptionV2",
]
