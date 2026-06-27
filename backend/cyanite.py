"""基础设施 · Cyanite REST 封装。全项目唯一碰网络的地方。

编排层只调这里的函数；测试时 monkeypatch 本模块即可离线跑。
REST 形态取自 notebooks/cyanite_model_outputs.ipynb。
"""
from __future__ import annotations
import csv
import pathlib

import requests

import config

_DATA = pathlib.Path(__file__).resolve().parents[1] / "data" / "tracks.csv"

# 数据包 Jamendo id <-> Cyanite id，以及展示信息，启动时载入一次
_JAM_TO_CYAN: dict[str, str] = {}
_DISPLAY: dict[str, dict] = {}
with _DATA.open() as f:
    for row in csv.DictReader(f):
        _JAM_TO_CYAN[row["track_id"]] = row["cyanite_id"]
        _DISPLAY[row["cyanite_id"]] = {
            "track_id": row["track_id"],
            "cyanite_id": row["cyanite_id"],
            "title": row.get("name", ""),
            "artist": row.get("artist_name", ""),
        }
_CYAN_TO_JAM = {c: j for j, c in _JAM_TO_CYAN.items()}

_session = requests.Session()
_session.headers.update({"x-api-key": config.CYANITE_API_KEY})


# --- id / 展示 ---
def to_cyanite(track_id: str) -> str:
    return _JAM_TO_CYAN[str(track_id)]


def to_jamendo(cyanite_id: str) -> str:
    return _CYAN_TO_JAM[cyanite_id]


def display(cyanite_id: str) -> dict:
    return _DISPLAY.get(cyanite_id, {"track_id": "", "cyanite_id": cyanite_id, "title": "", "artist": ""})


def normalize(resp: dict) -> list[dict]:
    """Cyanite {items:[{track,score}]} -> [{cyanite_id, score}]。"""
    out = []
    for it in resp.get("items", []):
        track = it.get("track", it)
        out.append({"cyanite_id": track.get("id"), "score": it.get("score")})
    return out


# --- 检索 ---
def search_by_prompt(query: str, limit: int = config.SEARCH_LIMIT) -> list[dict]:
    """freeTextSearch：自然语言 -> 候选曲。"""
    r = _session.post(f"{config.CYANITE_BASE_URL}/private-alpha/library-tracks/search",
                      params={"limit": limit}, json={"query": query}, timeout=60)
    r.raise_for_status()
    return normalize(r.json())


def find_similar(cyanite_id: str, limit: int = config.SIMILAR_LIMIT) -> list[dict]:
    """similarById：一首曲 -> 声学相似曲。"""
    r = _session.post(f"{config.CYANITE_BASE_URL}/private-alpha/library-tracks/{cyanite_id}/similar",
                      params={"limit": limit}, json={}, timeout=60)
    r.raise_for_status()
    return normalize(r.json())


def model_tags(cyanite_id: str, models: list[str]) -> dict:
    """拉某曲的模型标签，给 'Why this track?' 用。"""
    params = [("model", m) for m in models]
    r = _session.get(f"{config.CYANITE_BASE_URL}/library-tracks/{cyanite_id}/models",
                     params=params, timeout=60)
    r.raise_for_status()
    return r.json()
