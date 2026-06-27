"""Minimal Cyanite *tagging* client (the only Cyanite call the memory module needs).

GET /library-tracks/{id}/models  -> {"items": [<model output>, ...]}

Includes a disk cache (fetch each track once — shared quota), a conservative
rate limiter, and 429 backoff. Search endpoints are intentionally out of scope
here; they belong to the /feedback teammate.
"""
import hashlib
import json
import os
import threading
import time
from collections import deque

import requests

from . import config

_TAGGING_PER_MIN = 110   # stay under the shared 180/min; many teams share the key
_calls = deque()
_lock = threading.Lock()

_session = requests.Session()
if config.CYANITE_API_KEY:
    _session.headers.update({"x-api-key": config.CYANITE_API_KEY})


def _cache_path(track_id, models):
    key = track_id + "|" + ",".join(sorted(models))
    h = hashlib.sha1(key.encode()).hexdigest()
    d = os.path.join(config.CACHE_DIR, "models")
    os.makedirs(d, exist_ok=True)
    return os.path.join(d, f"{h}.json")


def _throttle():
    with _lock:
        now = time.time()
        while _calls and now - _calls[0] > 60:
            _calls.popleft()
        if len(_calls) >= _TAGGING_PER_MIN:
            wait = 60 - (now - _calls[0]) + 0.1
        else:
            wait = 0
    if wait > 0:
        time.sleep(wait)
        return _throttle()
    with _lock:
        _calls.append(time.time())


def get_model_outputs(track_id, models=None):
    """Cached, rate-limited tagging fetch. Returns {"items": [...]}.
    In MOCK mode (no key) returns a deterministic fake so the module is testable."""
    models = models or config.PROFILE_MODELS
    p = _cache_path(track_id, models)
    if os.path.exists(p):
        with open(p) as f:
            return json.load(f)

    if config.MOCK:
        out = _mock(track_id, models)
    else:
        out = _fetch(track_id, models)

    with open(p, "w") as f:
        json.dump(out, f)
    return out


def _fetch(track_id, models, retries=4):
    url = f"{config.CYANITE_BASE_URL}/library-tracks/{track_id}/models"
    params = [("model", m) for m in models]
    for attempt in range(retries):
        _throttle()
        r = _session.get(url, params=params, timeout=60)
        if r.status_code == 429:
            time.sleep(2 ** attempt + 1)
            continue
        r.raise_for_status()
        return r.json()
    r.raise_for_status()
    return r.json()


def _mock(track_id, models):
    import random
    rng = random.Random(int(hashlib.sha1(track_id.encode()).hexdigest(), 16))
    moods = ["calm", "ethereal", "dark", "energetic", "happy", "chill"]
    genres = ["ambient", "electronic", "jazz", "rock", "classical"]
    insts = ["synth", "piano", "strings", "drumKit", "acousticGuitar"]
    items = []
    for m in models:
        if m == "MoodSimpleV2":
            items.append({"version": m, "tags": rng.sample(moods, 2)})
        elif m == "MainGenreV2":
            items.append({"version": m, "tags": [rng.choice(genres)]})
        elif m == "InstrumentsV2":
            items.append({"version": m, "tags": rng.sample(insts, 3)})
        elif m == "CharacterV2":
            items.append({"version": m, "tags": rng.sample(["warm", "cool", "ethereal"], 2)})
        elif m == "MovementV2":
            items.append({"version": m, "tags": [rng.choice(["flowing", "driving", "groovy"])]})
        elif m == "BpmV2":
            items.append({"version": m, "tag": rng.randint(70, 140)})
        elif m == "TempoV1":
            items.append({"version": m, "tag": rng.choice(["slow", "medium", "fast"])})
        elif m == "ValenceArousalV2":
            items.append({"version": m, "scores": {"valence": round(rng.uniform(-1, 1), 2),
                                                   "arousal": round(rng.uniform(-1, 1), 2)},
                          "energyLevel": rng.choice(["low", "medium", "high"])})
        elif m == "MusicalEraV2":
            items.append({"version": m, "tag": "contemporary"})
        elif m == "VocalsV2":
            items.append({"version": m, "tags": [rng.choice(["instrumental", "female", "male"])]})
        elif m == "AutoDescriptionV2":
            items.append({"version": m, "description": "A calm, atmospheric track."})
    return {"items": items}
