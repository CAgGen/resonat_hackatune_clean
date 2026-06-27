"""Normalize raw Cyanite model outputs into a flat TrackTags dict."""
from . import cyanite_tags


def _iter(outputs):
    if isinstance(outputs, dict) and isinstance(outputs.get("items"), list):
        yield from outputs["items"]
    elif isinstance(outputs, list):
        yield from outputs


def normalize(outputs) -> dict:
    t = {"moods": [], "genres": [], "instruments": [], "character": [],
         "movement": [], "bpm": None, "tempo": None, "valence": None,
         "arousal": None, "energy": None, "era": None, "vocals": [],
         "description": None}
    for mo in _iter(outputs):
        v = mo.get("version")
        if v == "MoodSimpleV2":
            t["moods"] = mo.get("tags") or []
        elif v == "MainGenreV2":
            t["genres"] = mo.get("tags") or []
        elif v == "InstrumentsV2":
            t["instruments"] = mo.get("tags") or []
        elif v == "CharacterV2":
            t["character"] = mo.get("tags") or []
        elif v == "MovementV2":
            t["movement"] = mo.get("tags") or []
        elif v == "BpmV2":
            t["bpm"] = mo.get("tag")
        elif v == "TempoV1":
            t["tempo"] = mo.get("tag")
        elif v == "ValenceArousalV2":
            sc = mo.get("scores") or {}
            t["valence"], t["arousal"] = sc.get("valence"), sc.get("arousal")
            t["energy"] = mo.get("energyLevel")
        elif v == "MusicalEraV2":
            t["era"] = mo.get("tag")
        elif v == "VocalsV2":
            t["vocals"] = mo.get("tags") or []
        elif v == "AutoDescriptionV2":
            t["description"] = mo.get("description")
    return t


def for_track(track_id, models=None) -> dict:
    """Cached, normalized tags for one Cyanite track id (libtr_...)."""
    return normalize(cyanite_tags.get_model_outputs(track_id, models))
