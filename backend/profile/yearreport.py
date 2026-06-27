"""Music "Year in Sound" — a Spotify-Wrapped-style emotional yearbook built from a
user's taste memory + Cyanite mood analysis.

It surfaces moments like
  "11月14日 凌晨3点，你听了《…》 — 那天夜里，你是不是藏着心事？"
where the reflective half-sentence is chosen from the track's Cyanite mood.

IMPORTANT: the data pack has no real listening timestamps. We SIMULATE a plausible
timeline by biasing each track's time-of-day from its mood (melancholic → late
night, energetic → daytime), so the narrative is self-consistent. In a real
product, plug in real play history instead of _synth_time().

    python -m backend.profile.yearreport [user_id] [year]
"""
import hashlib
import os
import sys
from collections import Counter, defaultdict

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm

from . import data, tags as tagmod, mdmemory

OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "analysis")
os.makedirs(OUT_DIR, exist_ok=True)

# pick a CJK-capable font so Chinese text renders (not tofu boxes)
for _f in ("PingFang SC", "Arial Unicode MS", "Hiragino Sans GB", "Heiti SC"):
    if _f in {f.name for f in fm.fontManager.ttflist}:
        plt.rcParams["font.sans-serif"] = [_f]
        break
plt.rcParams["axes.unicode_minus"] = False

# mood -> a reflective half-sentence (the emotional hook)
MOOD_LINE = {
    "sad": "That night — were you carrying something on your mind?",
    "dark": "Late at night, you sank alone into a certain mood.",
    "calm": "In that moment, you just wanted the world to go quiet.",
    "chill": "You slowed the pace down and let your mind drift.",
    "energetic": "That day, you were full of drive.",
    "happy": "Your mood that day was probably a good one.",
    "uplifting": "You needed a little lift.",
    "romantic": "Maybe, in that moment, someone came to mind.",
    "sexy": "That night had a warm, intimate charge to it.",
    "ethereal": "You drifted off into a little world of your own.",
    "epic": "You scored your day like an epic.",
    "scary": "You needed to let the feeling out.",
    "aggressive": "That day you wanted to smash something.",
}
# mood -> hours it tends to happen (for the simulated timeline)
MOOD_HOURS = {
    "sad": (0, 4), "dark": (22, 26), "ethereal": (23, 27), "calm": (22, 25),
    "chill": (20, 24), "romantic": (19, 23), "sexy": (21, 25),
    "energetic": (8, 18), "happy": (10, 19), "uplifting": (7, 12),
    "epic": (15, 21), "scary": (1, 4), "aggressive": (16, 22),
}
MOOD_COLOR = {
    "sad": "#4C72B0", "dark": "#3b3b5c", "calm": "#55A868", "chill": "#64B5CD",
    "energetic": "#DD8452", "happy": "#E8C13B", "uplifting": "#8DD3C7",
    "romantic": "#C44E52", "sexy": "#A6418C", "ethereal": "#8172B3",
    "epic": "#937860", "scary": "#7f1d1d", "aggressive": "#b03030",
}
_DAYS = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]


def _rng(seed):
    import random
    return random.Random(int(hashlib.sha1(seed.encode()).hexdigest(), 16))


def _synth_time(cyanite_id, mood):
    """Deterministic, mood-biased (month, day, hour) for a track. SIMULATED."""
    r = _rng(cyanite_id)
    month = r.randint(1, 12)
    day = r.randint(1, _DAYS[month - 1])
    lo, hi = MOOD_HOURS.get(mood, (0, 24))
    hour = r.randint(lo, hi - 1) % 24
    return month, day, hour


def build_report(user_id, year=2025):
    liked = mdmemory.seed_pool(user_id) or data.user_liked_cyanite(user_id)
    events = []
    for cid in liked:
        try:
            t = tagmod.for_track(cid)
        except Exception:
            continue
        mood = (t.get("moods") or ["calm"])[0]
        m, d, h = _synth_time(cid, mood)
        disp = data.track_display(cid)
        events.append({"cid": cid, "mood": mood, "hour": h, "month": m, "day": d,
                       "valence": t.get("valence"), "arousal": t.get("arousal"),
                       "name": disp.get("name") or cid[-6:], "artist": disp.get("artist")})
    if not events:
        raise SystemExit(f"no listening data for {user_id}")

    moods = Counter(e["mood"] for e in events)
    hour_mood = defaultdict(Counter)
    for e in events:
        hour_mood[e["hour"]][e["mood"]] += 1

    # fabricated total plays for the year (likes are saves, not plays)
    plays = int(len(events) * _rng(user_id + "plays").uniform(38, 72))

    MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
              "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

    # pick highlight moments
    def fmt(e):
        h = e["hour"]
        h12 = h % 12 or 12
        ampm = "AM" if h < 12 else "PM"
        who = f" — {e['artist']}" if e["artist"] else ""
        line = MOOD_LINE.get(e["mood"], "")
        return (f"{MONTHS[e['month']-1]} {e['day']}, {h12} {ampm} — you played «{e['name']}»{who}", line)

    night = [e for e in events if e["hour"] < 5 or e["hour"] >= 22]
    candidates = [
        min(events, key=lambda e: e["valence"] if e["valence"] is not None else 0),  # most melancholic
        (max(night, key=lambda e: e["hour"]) if night else None),                    # deep night
        max(events, key=lambda e: e["arousal"] if e["arousal"] is not None else 0),  # most energetic
        next((e for e in events if e["mood"] == "romantic"), None),                  # romantic
        next((e for e in events if e["mood"] in ("happy", "uplifting", "chill")), None),
    ]
    moments, seen, used_lines = [], set(), set()
    for pick in candidates:
        if not pick or pick["cid"] in seen:
            continue
        line = MOOD_LINE.get(pick["mood"], "")
        if line and line in used_lines:      # avoid repeating the same sentence
            continue
        seen.add(pick["cid"]); used_lines.add(line); moments.append(fmt(pick))
        if len(moments) >= 4:
            break

    return {"user_id": user_id, "year": year, "n": len(events), "plays": plays,
            "top_moods": moods.most_common(5), "hour_mood": hour_mood,
            "moments": moments, "headline_mood": moods.most_common(1)[0][0]}


def render_report(user_id, year=2025, out=None):
    rep = build_report(user_id, year)
    fig = plt.figure(figsize=(15, 7.5))
    fig.suptitle(f"Your Year in Sound · {year}    —    user {user_id}",
                 fontsize=15, fontweight="bold")

    # left: 24h emotional clock (polar), bar per hour colored by dominant mood
    ax = fig.add_subplot(1, 2, 1, projection="polar")
    ax.set_theta_zero_location("N"); ax.set_theta_direction(-1)
    import math
    for h in range(24):
        c = rep["hour_mood"].get(h)
        if not c:
            continue
        total = sum(c.values())
        mood = c.most_common(1)[0][0]
        ax.bar(h * math.pi / 12, total, width=math.pi / 12 * 0.9,
               color=MOOD_COLOR.get(mood, "#999"), alpha=0.85)
    ax.set_xticks([i * math.pi / 12 for i in range(0, 24, 3)])
    ax.set_xticklabels([f"{i}:00" for i in range(0, 24, 3)])
    ax.set_yticklabels([])
    ax.set_title("Emotional clock — when in the day, and in what mood, you listen",
                 fontsize=11, pad=18)

    # right: headline + moments + top moods
    ax2 = fig.add_subplot(1, 2, 2); ax2.axis("off")
    y = 0.96
    ax2.text(0, y, f"This year you played {rep['plays']:,} tracks and saved "
             f"{rep['n']} — your keynote mood was «{rep['headline_mood']}»",
             fontsize=12, fontweight="bold", transform=ax2.transAxes); y -= 0.1
    ax2.text(0, y, "Your highlight moments:", fontsize=12, fontweight="bold",
             transform=ax2.transAxes); y -= 0.08
    for head, line in rep["moments"]:
        ax2.text(0.02, y, "• " + head, fontsize=11, transform=ax2.transAxes); y -= 0.06
        if line:
            ax2.text(0.05, y, line, fontsize=10, style="italic", color="#555",
                     transform=ax2.transAxes); y -= 0.075
        y -= 0.015
    y -= 0.02
    ax2.text(0, y, "Mood keywords:  " +
             "   ".join(f"{m} ×{n}" for m, n in rep["top_moods"]),
             fontsize=11, transform=ax2.transAxes); y -= 0.07
    ax2.text(0, 0.02, "(timeline is simulated from mood · plug in real play history "
             "in production)", fontsize=8, color="#999", transform=ax2.transAxes)

    plt.tight_layout(rect=[0, 0, 1, 0.94])
    out = out or os.path.join(OUT_DIR, f"yearreport_{mdmemory._safe(user_id)}.png")
    plt.savefig(out, dpi=130)
    return out, rep


if __name__ == "__main__":
    uid = sys.argv[1] if len(sys.argv) > 1 else "exp_4006097"
    yr = int(sys.argv[2]) if len(sys.argv) > 2 else 2025
    path, rep = render_report(uid, yr)
    print(f"=== 你的年度听感 {yr} · {uid} ===")
    print(f"{rep['n']} 首 · 主旋律「{rep['headline_mood']}」 · top moods {rep['top_moods']}\n")
    for head, line in rep["moments"]:
        print(" •", head)
        if line:
            print("   ", line)
    print("\nsaved:", path)
