/**
 * Memo · Music — Card grid (self-contained, drop-in)
 * ---------------------------------------------------------------------------
 * One file. No dependencies. Injects its own CSS + webfont on first use.
 *
 * ESM:
 *   import { renderCardGrid } from "./music-cards.js";
 *   renderCardGrid(document.getElementById("cards"), tracks, { coverBase: "pic/" });
 *
 * Plain <script> (no bundler):
 *   <script src="music-cards.js"></script>
 *   <script>MusicCards.renderCardGrid(el, tracks, { coverBase: "pic/" });</script>
 *
 * track = { track, artist, cover?, keywords?, onSelect?, onVote? }
 *   - cover      explicit image URL; if omitted, a random one from the pool is used
 *   - onSelect(track)            fired when the card body is clicked
 *   - onVote(track, value)       value = "like" | null (un-liked) | "dislike"
 *
 * renderCardGrid(container, tracks, opts)
 *   opts.coverBase   string prepended to every pooled filename (default "pic/")
 *   opts.covers      override the filename pool entirely (array of URLs)
 *   opts.randomCovers  default true — fill empty covers from the pool
 *   opts.onSelect / opts.onVote   defaults applied to every card
 * ---------------------------------------------------------------------------
 */
(function (root, factory) {
  const api = factory();
  if (typeof module === "object" && module.exports) module.exports = api; // CommonJS
  root.MusicCards = api;                                                  // global
})(typeof self !== "undefined" ? self : this, function () {

  /* ---- one-time CSS + font injection ---- */
  const STYLE_ID = "music-cards-styles";
  const CSS = `
  .mc-grid{
    --mc-card:#EFEDE6; --mc-ink:#2B2A26; --mc-ink-soft:#9A968B;
    --mc-placeholder:#C9C6BD; --mc-radius:3px;
    --mc-like:#ED2024; --mc-dislike:#1B1B1B;
    --mc-font:"Playfair Display",Georgia,serif;
    display:grid; grid-template-columns:repeat(auto-fill,minmax(220px,1fr)); gap:28px;
    font-family:var(--mc-font); color:var(--mc-ink);
  }
  .mc-card{
    background:var(--mc-card); border-radius:var(--mc-radius); overflow:hidden;
    border:none; width:100%; padding:0; font:inherit; color:inherit; text-align:left;
    cursor:pointer; display:flex; flex-direction:column;
    transition:transform .16s ease, box-shadow .16s ease;
  }
  .mc-card:hover{transform:translateY(-3px); box-shadow:0 10px 26px rgba(43,42,38,.12)}
  .mc-card:focus-visible{outline:2px solid var(--mc-ink); outline-offset:3px}
  .mc-cover{position:relative; width:100%; aspect-ratio:1/1; background:var(--mc-placeholder); overflow:hidden}
  .mc-cover img{position:absolute; inset:0; width:100%; height:100%; object-fit:cover; display:block}
  .mc-body{padding:14px 14px 10px; display:flex; flex-direction:column; flex:1}
  .mc-title{
    font-size:18px; font-weight:700; line-height:1.18;
    display:-webkit-box; -webkit-line-clamp:2; -webkit-box-orient:vertical; overflow:hidden;
    min-height:calc(2 * 1.18 * 18px);
  }
  .mc-artist{
    font-size:13px; font-style:italic; color:var(--mc-ink-soft); line-height:1.3; margin-top:4px;
    white-space:nowrap; overflow:hidden; text-overflow:ellipsis;
  }
  .mc-actions{margin-top:auto; padding-top:12px; display:flex; justify-content:flex-end; gap:4px}
  .mc-act{
    background:none; border:none; cursor:pointer; width:34px; height:34px; border-radius:var(--mc-radius);
    display:flex; align-items:center; justify-content:center; color:var(--mc-ink-soft);
    transition:background .14s ease, color .14s ease, transform .14s ease;
  }
  .mc-act svg{width:20px; height:20px; stroke:currentColor; fill:none; stroke-width:1.8; stroke-linecap:round; stroke-linejoin:round}
  .mc-act:active{transform:scale(.88)}
  .mc-like:hover{color:var(--mc-like); background:rgba(237,32,36,.08)}
  .mc-like.is-active{color:var(--mc-like)}
  .mc-like.is-active svg{fill:var(--mc-like)}
  .mc-dislike:hover{color:var(--mc-dislike); background:rgba(27,27,27,.07)}
  .mc-spark{position:fixed; border-radius:50%; background:var(--mc-like); pointer-events:none; z-index:9999; will-change:transform,opacity}
  @media (prefers-reduced-motion:reduce){.mc-card,.mc-act{transition:none}}
  `;

  function injectStyles() {
    if (typeof document === "undefined" || document.getElementById(STYLE_ID)) return;
    // Webfont (no-op if the page already loads Playfair Display)
    const link = document.createElement("link");
    link.rel = "stylesheet";
    link.href = "https://fonts.googleapis.com/css2?family=Playfair+Display:ital,wght@0,400;0,700;1,400&display=swap";
    document.head.appendChild(link);
    const style = document.createElement("style");
    style.id = STYLE_ID;
    style.textContent = CSS;
    document.head.appendChild(style);
  }

  /* ---- default cover pool (filenames only — see opts.coverBase) ---- */
  const COVER_POOL = [
    "100057absdl.jpg","1002710ilsdl.jpg","100539absdl.jpg","101965absdl.jpg",
    "105470absdl.jpg","105710absdl.jpg","106042absdl.jpg","255411fgsdl.jpg",
    "255654fgsdl.jpg","501995ldsdl.jpg","516645ldsdl.jpg","600451slsdl.jpg",
    "600454slsdl.jpg","604655slsdl.jpg","62427drsdl.jpg","912468absdl.jpg",
    "913209absdl.jpg","913281absdl.jpg","913542absdl.jpg","962703ilsdl.jpg",
    "962887ilsdl.jpg","963027ilsdl.jpg","963042ilsdl.jpg",
  ];

  function makeCoverPicker(pool) {
    let deck = [];
    const reshuffle = () => {
      deck = pool.slice();
      for (let i = deck.length - 1; i > 0; i--) {
        const j = Math.floor(Math.random() * (i + 1));
        [deck[i], deck[j]] = [deck[j], deck[i]];
      }
    };
    return () => { if (deck.length === 0) reshuffle(); return deck.pop(); };
  }

  const ICON_HEART = '<svg viewBox="0 0 24 24"><path d="M12 21.35l-1.45-1.32C5.4 15.36 2 12.28 2 8.5 2 5.42 4.42 3 7.5 3c1.74 0 3.41.81 4.5 2.09C13.09 3.81 14.76 3 16.5 3 19.58 3 22 5.42 22 8.5c0 3.78-3.4 6.86-8.55 11.54L12 21.35z"/></svg>';
  const ICON_DISLIKE = '<svg viewBox="0 0 24 24"><path d="M18 6 6 18M6 6l12 12"/></svg>';
  const reduceMotion = typeof window !== "undefined" &&
    window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  function burstAt(x, y) {
    if (reduceMotion) return;
    const N = 16;
    for (let i = 0; i < N; i++) {
      const p = document.createElement("div");
      p.className = "mc-spark";
      const size = 4 + Math.random() * 5;
      p.style.left = x + "px"; p.style.top = y + "px";
      p.style.width = size + "px"; p.style.height = size + "px";
      document.body.appendChild(p);
      const angle = (i / N) * Math.PI * 2 + Math.random() * 0.5;
      const dist = 24 + Math.random() * 34;
      const dx = Math.cos(angle) * dist, dy = Math.sin(angle) * dist;
      const dur = 550 + Math.random() * 350;
      p.animate([
        { transform: "translate(-50%,-50%) translate(0,0) scale(1)", opacity: 1 },
        { transform: `translate(-50%,-50%) translate(${dx}px,${dy + 10}px) scale(0)`, opacity: 0 },
      ], { duration: dur, easing: "cubic-bezier(.18,.7,.3,1)", fill: "forwards" });
      setTimeout(() => p.remove(), dur + 60);
    }
  }

  function makeLikeButton(track, onVote) {
    const btn = document.createElement("button");
    btn.type = "button"; btn.className = "mc-act mc-like";
    btn.setAttribute("aria-label", "Like"); btn.setAttribute("aria-pressed", "false");
    btn.innerHTML = ICON_HEART;
    btn.addEventListener("click", (e) => {
      e.stopPropagation();
      const liked = !btn.classList.contains("is-active");
      btn.classList.toggle("is-active", liked);
      btn.setAttribute("aria-pressed", String(liked));
      if (liked) {
        if (!reduceMotion) {
          btn.querySelector("svg").animate(
            [{ transform: "scale(1)" }, { transform: "scale(1.35)" }, { transform: "scale(1)" }],
            { duration: 320, easing: "cubic-bezier(.34,1.56,.64,1)" });
        }
        const r = btn.getBoundingClientRect();
        burstAt(r.left + r.width / 2, r.top + r.height / 2);
      }
      if (typeof onVote === "function") onVote(track, liked ? "like" : null);
    });
    return btn;
  }

  function makeDislikeButton(card, track, onVote) {
    const btn = document.createElement("button");
    btn.type = "button"; btn.className = "mc-act mc-dislike";
    btn.setAttribute("aria-label", "Not interested");
    btn.innerHTML = ICON_DISLIKE;
    btn.addEventListener("click", (e) => {
      e.stopPropagation();
      if (typeof onVote === "function") onVote(track, "dislike");
      dismissCard(card);
    });
    return btn;
  }

  function dismissCard(card) {
    const grid = card.parentNode;
    if (!grid) return;
    const siblings = Array.prototype.slice.call(grid.children);
    const firstRects = new Map(siblings.map((el) => [el, el.getBoundingClientRect()]));
    const finish = () => {
      card.remove();
      siblings.forEach((el) => {
        if (el === card) return;
        const first = firstRects.get(el), last = el.getBoundingClientRect();
        const dx = first.left - last.left, dy = first.top - last.top;
        if (dx || dy) {
          el.animate(
            [{ transform: `translate(${dx}px, ${dy}px)` }, { transform: "translate(0,0)" }],
            { duration: 420, easing: "cubic-bezier(.2,.7,.3,1)" });
        }
      });
    };
    if (reduceMotion) { finish(); return; }
    card.style.pointerEvents = "none";
    const FLY = 380;
    card.animate([
      { transform: "translate(0,0) rotate(0) scale(1)", opacity: 1 },
      { transform: "translate(28px,-34px) rotate(7deg) scale(.78)", opacity: 0 },
    ], { duration: FLY, easing: "cubic-bezier(.4,0,.6,1)", fill: "forwards" });
    setTimeout(finish, FLY);
  }

  function createCard(track) {
    injectStyles();
    const { track: name = "Track Name", artist = "Artist", cover, onSelect, onVote } = track;
    const card = document.createElement("article");
    card.className = "mc-card";
    card.tabIndex = 0; card.setAttribute("role", "button");
    card.setAttribute("aria-label", name + " by " + artist);

    const coverEl = document.createElement("div");
    coverEl.className = "mc-cover";
    if (cover) {
      const img = document.createElement("img");
      img.src = cover; img.alt = name + " cover art"; img.loading = "lazy";
      coverEl.appendChild(img);
    }

    const body = document.createElement("div");
    body.className = "mc-body";
    const titleEl = document.createElement("div");
    titleEl.className = "mc-title"; titleEl.textContent = name;
    const artistEl = document.createElement("div");
    artistEl.className = "mc-artist"; artistEl.textContent = "by " + artist;
    const actions = document.createElement("div");
    actions.className = "mc-actions";
    actions.append(makeLikeButton(track, onVote), makeDislikeButton(card, track, onVote));
    body.append(titleEl, artistEl, actions);
    card.append(coverEl, body);

    if (typeof onSelect === "function") card.addEventListener("click", () => onSelect(track));
    return card;
  }

  function renderCardGrid(container, tracks, opts) {
    if (!container) throw new Error("renderCardGrid: container is required");
    injectStyles();
    opts = opts || {};
    const randomCovers = opts.randomCovers !== false;
    const base = opts.coverBase != null ? opts.coverBase : "pic/";
    const pool = (opts.covers || COVER_POOL).map((f) => (opts.covers ? f : base + f));
    const pick = randomCovers ? makeCoverPicker(pool) : null;

    container.classList.add("mc-grid");
    const cards = (tracks || []).map((t) => {
      const merged = Object.assign({}, t);
      if (opts.onSelect && !merged.onSelect) merged.onSelect = opts.onSelect;
      if (opts.onVote && !merged.onVote) merged.onVote = opts.onVote;
      if (pick && !merged.cover) merged.cover = pick();
      return createCard(merged);
    });
    container.replaceChildren.apply(container, cards);
    return container;
  }

  return { createCard, renderCardGrid, COVER_POOL };
});
