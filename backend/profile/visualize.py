"""Render a user's taste memory as a visual "Taste Card" (PNG).

Four panels, all read straight from the stored memory:
  1. Top tags per dimension (mood / genre / instrument / character) as % bars
  2. Valence x Arousal position — where this listener sits on the emotion map
  3. Distinctive-to-you tags (IDF-weighted) — what makes the taste characteristic
  4. Anchor tracks — bubble size = reinforcement count, x = novelty

    python -m backend.profile.visualize [user_id]
"""
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from . import mdmemory

OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "analysis")
os.makedirs(OUT_DIR, exist_ok=True)

DIM_COLOR = {"moods": "#4C72B0", "genres": "#DD8452", "instruments": "#55A868",
             "character": "#C44E52", "movement": "#8172B3"}


def render_card(user_id, out=None):
    st = mdmemory.load(user_id)
    s = mdmemory.summary(user_id, _state=st)
    if not any(s["likes"].values()):
        raise SystemExit(f"no memory for {user_id} yet")

    fig, ax = plt.subplots(2, 2, figsize=(15, 10))
    fig.suptitle(f"Taste Card — user {user_id}    ·    {s['headline']}",
                 fontsize=13, fontweight="bold")

    # --- 1) top tags per dimension --------------------------------------------
    a = ax[0, 0]
    rows, colors = [], []
    for dim in ["moods", "genres", "instruments", "character"]:
        for x in s["likes"][dim][:4]:
            rows.append((f"{x['tag']}", x["pct"]))
            colors.append(DIM_COLOR[dim])
    rows = rows[::-1]; colors = colors[::-1]
    a.barh([r[0] for r in rows], [r[1] for r in rows], color=colors)
    a.set_title("What you like (share within each dimension)")
    a.set_xlabel("%")
    handles = [plt.Rectangle((0, 0), 1, 1, color=c) for c in DIM_COLOR.values()]
    a.legend(handles, DIM_COLOR.keys(), fontsize=8, loc="lower right")

    # --- 2) valence x arousal position ----------------------------------------
    a = ax[0, 1]
    v = s["numeric"].get("valence") or 0.0
    ar = s["numeric"].get("arousal") or 0.0
    a.axhline(0, color="grey", lw=0.6); a.axvline(0, color="grey", lw=0.6)
    a.set_xlim(-1, 1); a.set_ylim(-1, 1)
    for q, (qx, qy) in {"happy / energetic": (.55, .8), "tense / dark": (-.6, .8),
                        "sad / low": (-.65, -.85), "calm / serene": (.55, -.85)}.items():
        a.text(qx, qy, q, fontsize=8, alpha=0.45, ha="center")
    a.scatter([v], [ar], s=420, color="#C44E52", edgecolor="black", zorder=3)
    a.annotate("you", (v, ar), fontsize=10, fontweight="bold",
               ha="center", va="center", color="white", zorder=4)
    a.set_title("Your emotional centre (valence × arousal)")
    a.set_xlabel("valence  (negative → positive)")
    a.set_ylabel("arousal  (calm → intense)")

    # --- 3) distinctive-to-you (IDF) ------------------------------------------
    a = ax[1, 0]
    dist = s["distinctive"][::-1]
    if dist:
        a.barh([d["tag"] for d in dist], [d["idf"] for d in dist], color="#937860")
    a.set_title("Distinctive to you (rare in catalog = high IDF)")
    a.set_xlabel("IDF (higher = more characteristic)")

    # --- 4) anchor tracks ------------------------------------------------------
    a = ax[1, 1]
    ex = s.get("exemplars", [])
    if ex:
        xs = [e["novelty"] * 100 for e in ex]
        ys = list(range(len(ex)))
        sizes = [60 + 90 * e["count"] for e in ex]
        a.scatter(xs, ys, s=sizes, alpha=0.6, color="#4C72B0", edgecolor="black")
        for i, e in enumerate(ex):
            lbl = ", ".join((e.get("distinctive") or [])[:2]) or e["track_id"][-6:]
            a.text(xs[i] + 1.5, ys[i], f"{lbl}  ×{e['count']}", fontsize=7, va="center")
        a.set_xlim(0, 110); a.set_ylim(-1, len(ex))
        a.set_yticks([])
    a.set_title(f"Anchor tracks — {len(ex)} taste regions (bubble = times reinforced)")
    a.set_xlabel("novelty when first stored (%)")

    plt.tight_layout(rect=[0, 0, 1, 0.96])
    out = out or os.path.join(OUT_DIR, f"profile_{mdmemory._safe(user_id)}.png")
    plt.savefig(out, dpi=130)
    return out


if __name__ == "__main__":
    uid = sys.argv[1] if len(sys.argv) > 1 else "exp_4006097"
    print("saved:", render_card(uid))
