"""Infrastructure · sponsor-provided user liked tracks.

data/users.csv uses Jamendo track_ids; business logic needs Cyanite ids for API calls.
"""
from __future__ import annotations

import csv
import pathlib

import cyanite

_DATA = pathlib.Path(__file__).resolve().parents[1] / "data" / "users.csv"

_USER_LIKES: dict[str, list[str]] = {}
with _DATA.open() as f:
    for row in csv.DictReader(f):
        _USER_LIKES[str(row["user_id"])] = [
            track_id for track_id in row.get("liked_track_ids", "").split() if track_id
        ]


def liked_cyanite_ids(user_id: str) -> list[str]:
    """Return provided liked tracks for a user as Cyanite ids."""
    out = []
    for track_id in _USER_LIKES.get(str(user_id), []):
        try:
            out.append(cyanite.to_cyanite(track_id))
        except KeyError:
            continue
    return out
