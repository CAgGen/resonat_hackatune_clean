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

# --- OpenAI ---
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
OPENAI_BASE_URL = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1")
OPENAI_MODEL = os.environ.get("OPENAI_MODEL", "gpt-5.4-nano")
OPENAI_TIMEOUT = int(os.environ.get("OPENAI_TIMEOUT", "20"))

# --- 编排旋钮 ---
VISIBLE_N = 5        # 推荐列表一次展示几首
SEARCH_LIMIT = 20    # freeText 召回上限
SIMILAR_LIMIT = 20   # like 后 similarById 召回上限

# --- 薄重排权重 · 护栏: W_PRIMARY > W_SOFT + W_NEG（音频/语义分必须主导）---
W_PRIMARY = 1.0
W_SOFT = 0.3
W_NEG = 0.3
