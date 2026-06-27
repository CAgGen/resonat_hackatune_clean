"""Tag salience / distinctiveness (the 'what to remember' filter).

A tag is worth remembering when it is BOTH present and *distinctive* — rare in the
catalog, not something every track has. We use an IDF-style weight from catalog
base rates (tag_base_rates.json, precomputed aggregate frequencies):

    idf(tag) = log(1 / freq(tag))     # common tag -> ~0, rare tag -> high

This makes the memory store characteristic elements ("asian flute") and skip the
obvious ones ("drums"), which is directly explainable.
"""
import json
import math
import os

_BASE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tag_base_rates.json")
FACET_DIMS = ("genres", "moods", "character")          # high-level taste facets
DETAIL_DIMS = ("instruments", "movement")              # finer texture
_rates = None


def _load():
    global _rates
    if _rates is None:
        _rates = json.load(open(_BASE)) if os.path.exists(_BASE) else {}
    return _rates


def idf(dim, tag):
    """Higher = rarer = more distinctive. Unknown tags treated as fairly rare."""
    f = _load().get(dim, {}).get(tag)
    if not f:
        return 2.0
    return round(math.log(1.0 / f), 3)


def distinctive_tags(tags, dims=FACET_DIMS + DETAIL_DIMS, min_idf=1.0, top=6):
    """Tags worth remembering: present AND distinctive (idf >= min_idf), ranked."""
    scored = []
    for d in dims:
        for t in tags.get(d) or []:
            w = idf(d, t)
            if w >= min_idf:
                scored.append({"dim": d, "tag": t, "idf": w})
    scored.sort(key=lambda x: -x["idf"])
    return scored[:top]


def facet_set(tags):
    """Set of high-level facet tags (genre/mood/character) for overlap/redundancy."""
    s = set()
    for d in FACET_DIMS:
        for t in tags.get(d) or []:
            s.add(f"{d[0]}:{t}")
    return s
