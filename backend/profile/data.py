"""Data-pack helpers: id mapping + audio url (used for demo/eval, not core memory).

In the live product, liked track ids arrive from search results and are already
Cyanite ids (libtr_...). This module only helps when seeding from the data-pack
users.csv, whose likes are Jamendo ids.
"""
import csv
import os

from . import config

_j2c, _c2j, _users = {}, {}, {}
_loaded = False


def load():
    global _loaded
    if _loaded:
        return
    with open(os.path.join(config.DATA_DIR, "tracks.csv")) as f:
        for r in csv.DictReader(f):
            _j2c[r["track_id"]] = r["cyanite_id"]
            _c2j[r["cyanite_id"]] = r["track_id"]
    upath = os.path.join(config.DATA_DIR, "users.csv")
    if os.path.exists(upath):
        with open(upath) as f:
            for r in csv.DictReader(f):
                _users[r["user_id"]] = (r.get("liked_track_ids") or "").split()
    _loaded = True


def jamendo_to_cyanite(jid):
    load(); return _j2c.get(str(jid))


def audio_url(cyanite_id):
    load()
    jid = _c2j.get(cyanite_id)
    return f"https://prod-1.storage.jamendo.com/download/track/{jid}/mp32/" if jid else None


def user_ids():
    load()
    return list(_users.keys())


def user_liked_cyanite(user_id):
    load()
    return [_j2c[j] for j in _users.get(str(user_id), []) if j in _j2c]
