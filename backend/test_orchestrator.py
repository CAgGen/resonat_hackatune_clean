"""编排框架自检。monkeypatch 三个接缝（cyanite / intent_compiler / memory），离线跑主循环。
新逻辑：普通模式 like 会划走并用该曲 similarById 回填；防沉迷模式 like 只记录不划走。
run: uv run pytest -v
"""
from fastapi.testclient import TestClient
import requests

import app
import orchestrator as orch

client = TestClient(app.app)

SEARCH = [{"cyanite_id": f"libtr_{i}", "score": 1.0 - i / 10} for i in range(8)]   # 8 首
SIMILAR = [{"cyanite_id": f"sim_{i}", "score": 0.9 - i / 10} for i in range(3)]    # 单种子相似
MULTI = [{"cyanite_id": f"multi_{i}", "score": 0.95 - i / 10} for i in range(3)]   # 多种子相似
PROFILE = [{"cyanite_id": f"profile_{i}", "score": 0.88 - i / 10} for i in range(3)]


def _fake_seams(monkeypatch, tmp_path):
    """返回计数器 dict，记录单种子 / 多种子相似各被调了几次。"""
    calls = {"similar": 0, "multi": 0, "search": []}
    monkeypatch.setattr(app.config, "CYANITE_API_KEY", "test-key")

    def fake_similar(cid, limit=20):
        calls["similar"] += 1
        calls.setdefault("similar_args", []).append((cid, limit))
        return SIMILAR

    def fake_multi(cids, limit=20):
        calls["multi"] += 1
        calls.setdefault("multi_args", []).append((tuple(cids), limit))
        return MULTI

    def fake_search(q, limit=20, metadata_filter=None):
        calls["search"].append((q, limit, metadata_filter))
        return PROFILE if limit == 10 else SEARCH

    monkeypatch.setattr(orch.cyanite, "search_by_prompt", fake_search)
    monkeypatch.setattr(orch.cyanite, "find_similar", fake_similar)
    monkeypatch.setattr(orch.cyanite, "find_similar_multi", fake_multi)
    monkeypatch.setattr(orch.cyanite, "display",
                        lambda cid, track_id="": {"track_id": track_id or cid, "cyanite_id": cid,
                                                  "title": "T", "artist": "A"})
    monkeypatch.setattr(orch.intent_agent, "compile_query_card",
                        lambda posts, profile_md="": {
                            "interpretation_plain": "test intent",
                            "free_text_query": "",
                            "metadata_filter": None,
                            "soft_targets": [],
                            "negatives": [],
                        })
    monkeypatch.setattr(orch.intent_agent, "search_args",
                        lambda posts, profile_md="": {"query": "test intent", "metadata_filter": None})
    monkeypatch.setattr(orch.memory, "_ev_path", lambda u: tmp_path / f"{u}.evidence.md")
    monkeypatch.setattr(orch.memory, "_mem_path", lambda u: tmp_path / f"{u}.memory.md")
    monkeypatch.setattr(orch.memory, "_feeling_tags", lambda cid: ["calm", "warm"])  # 不打网络
    monkeypatch.setattr(orch.memory, "_llm_profile", lambda info: None)              # 走确定性兜底
    monkeypatch.setattr(orch.user_profiles, "liked_cyanite_ids", lambda u: [])
    return calls


def _confirmed(user_id, monkeypatch, tmp_path):
    calls = _fake_seams(monkeypatch, tmp_path)
    sid = client.post("/intent", json={"text": "dark", "user_id": user_id}).json()["session_id"]
    client.post("/intent/confirm", json={"session_id": sid})
    return sid, calls


def test_intent_does_not_search_until_confirm(monkeypatch, tmp_path):
    hit = {"n": 0}
    _fake_seams(monkeypatch, tmp_path)
    monkeypatch.setattr(orch.cyanite, "search_by_prompt",
                        lambda q, limit=20, metadata_filter=None: hit.update(n=hit["n"] + 1) or SEARCH)
    sid = client.post("/intent", json={"text": "dark betrayal", "user_id": "u1"}).json()["session_id"]
    client.post("/intent/follow-up", json={"session_id": sid, "text": "more restrained"})
    assert hit["n"] == 0  # 确认门：确认前不检索


def test_confirm_fills_visible_and_backlog(monkeypatch, tmp_path):
    sid, _ = _confirmed("u1", monkeypatch, tmp_path)
    body = client.post("/intent/confirm", json={"session_id": sid}).json()
    assert len(body["cards"]) == orch.config.VISIBLE_N
    assert len(orch.SESSIONS[sid]["free_text_backlog"]) == len(SEARCH) - orch.config.VISIBLE_N


def test_surprise_card_only_in_confirm(monkeypatch, tmp_path):
    calls = _fake_seams(monkeypatch, tmp_path)
    monkeypatch.setattr(orch.memory, "read_memory", lambda u: "core feeling: flowing")  # 有画像可偏离
    monkeypatch.setattr(orch.intent_agent, "surprise_args",
                        lambda posts, profile_md="": {"query": "surprise", "metadata_filter": None})

    def search(q, limit=20, metadata_filter=None):
        calls["search"].append((q, limit, metadata_filter))
        return [{"cyanite_id": "surprise_hit", "score": 0.7}] if q == "surprise" else SEARCH
    monkeypatch.setattr(orch.cyanite, "search_by_prompt", search)

    sid = client.post("/intent", json={"text": "dark", "user_id": "us"}).json()["session_id"]
    cards = client.post("/intent/confirm", json={"session_id": sid}).json()["cards"]
    surprises = [c for c in cards if c["source"] == "surprise"]
    assert len(surprises) == 1 and surprises[0]["cyanite_id"] == "surprise_hit"
    assert len(cards) == orch.config.VISIBLE_N  # 仍 5 张：挤出的普通卡退回 backlog

    # like 惊喜卡 → 划走并用 similar 回填；回填的不再是惊喜
    client.post("/feedback", json={"session_id": sid, "track_id": "surprise_hit", "verdict": "like"})
    assert all(c["source"] != "surprise" for c in orch.SESSIONS[sid]["visible_cards"])


def test_no_surprise_without_profile(monkeypatch, tmp_path):
    sid, _ = _confirmed("noprof", monkeypatch, tmp_path)  # read_memory 为空 → 不出惊喜
    cards = client.post("/intent/confirm", json={"session_id": sid}).json()["cards"]
    assert all(c["source"] != "surprise" for c in cards)


def test_confirm_translates_cyanite_http_error(monkeypatch):
    monkeypatch.setattr(app.config, "CYANITE_API_KEY", "test-key")
    resp = requests.Response()
    resp.status_code = 401
    resp.url = "https://rest-api.cyanite.ai/v1/private-alpha/library-tracks/search?limit=20"

    def fail(_sid):
        raise requests.HTTPError("401 Client Error: Unauthorized", response=resp)

    monkeypatch.setattr(orch, "confirm", fail)
    body = client.post("/intent/confirm", json={"session_id": "sid"}).json()

    assert body["detail"].startswith("Cyanite 401")


def test_confirm_missing_cyanite_key_returns_503(monkeypatch):
    monkeypatch.setattr(app.config, "CYANITE_API_KEY", "")
    body = client.post("/intent/confirm", json={"session_id": "sid"}).json()

    assert body["detail"].startswith("CYANITE_API_KEY is missing")


def test_normal_like_swipes_and_refills_from_clicked_track_similarity(monkeypatch, tmp_path):
    sid, calls = _confirmed("u2", monkeypatch, tmp_path)
    before = [c["track_id"] for c in orch.SESSIONS[sid]["visible_cards"]]
    body = client.post("/feedback", json={"session_id": sid, "track_id": "libtr_0", "verdict": "like"}).json()
    assert calls["similar"] == 1                       # 普通 like 立刻用被 liked 曲搜相似
    assert calls["similar_args"] == [("libtr_0", 10)]
    assert orch.SESSIONS[sid]["liked_tracks"] == ["libtr_0"]
    ids = [c["track_id"] for c in body["cards"]]
    assert "libtr_0" not in ids                         # 被 liked 的卡划走
    assert "sim_0" in ids                               # 最高 similar_score 回填
    assert len(ids) == orch.config.VISIBLE_N
    assert ids != before
    assert not (tmp_path / "u2.evidence.md").exists()   # like 不落记忆（一轮结束才统一落）

    fin = client.post("/round/finish", json={"session_id": sid}).json()   # ⑦ 完成本轮
    assert (tmp_path / "u2.evidence.md").read_text(encoding="utf-8").count("\n- ") == 1  # 此刻才写 1 行
    assert "你的感觉" in fin["memory_md"]


def test_anti_addiction_like_records_without_swiping(monkeypatch, tmp_path):
    sid, calls = _confirmed("anti_like", monkeypatch, tmp_path)
    before = [c["track_id"] for c in orch.SESSIONS[sid]["visible_cards"]]
    body = client.post(
        "/feedback",
        json={
            "session_id": sid,
            "track_id": "libtr_0",
            "verdict": "like",
            "mode": "anti_addiction",
        },
    ).json()

    assert calls["similar"] == 0
    assert orch.SESSIONS[sid]["liked_tracks"] == ["libtr_0"]
    assert [c["track_id"] for c in body["cards"]] == before


def test_anti_addiction_dislike_refills_from_profile_semantic_search(monkeypatch, tmp_path):
    sid, calls = _confirmed("anti_dislike", monkeypatch, tmp_path)
    client.post(
        "/feedback",
        json={
            "session_id": sid,
            "track_id": "libtr_0",
            "verdict": "like",
            "mode": "anti_addiction",
        },
    )
    body = client.post(
        "/feedback",
        json={
            "session_id": sid,
            "track_id": "libtr_1",
            "verdict": "dislike",
            "mode": "anti_addiction",
        },
    ).json()

    assert calls["search"][-1][1] == 10
    assert calls["similar"] == 0
    ids = [c["track_id"] for c in body["cards"]]
    assert "libtr_1" not in ids
    assert "profile_0" in ids
    refill = next(c for c in body["cards"] if c["track_id"] == "profile_0")
    assert refill["source"] == "profile_semantic"
    assert len(ids) == orch.config.VISIBLE_N


def test_dislike_with_one_like_uses_single_seed(monkeypatch, tmp_path):
    sid, calls = _confirmed("u3", monkeypatch, tmp_path)
    client.post("/feedback", json={"session_id": sid, "track_id": "libtr_0", "verdict": "like"})
    assert calls["similar"] == 1 and calls["multi"] == 0   # like 已用被点击曲搜相似
    body = client.post("/feedback", json={"session_id": sid, "track_id": "libtr_1", "verdict": "dislike"}).json()
    assert calls["similar"] == 1 and calls["multi"] == 0   # liked 集合没变 → 复用候选池
    ids = [c["track_id"] for c in body["cards"]]
    assert "libtr_1" not in ids                            # 被移除
    assert "sim_0" in ids                                  # 最高 similar_score 回填
    refill = next(c for c in body["cards"] if c["track_id"] == "sim_0")
    assert "final_score" not in refill and "ranking_basis" not in refill  # debug metadata 不给前端
    assert len(ids) == orch.config.VISIBLE_N               # 槽位数不变


def test_normal_likes_use_clicked_track_similarity_without_multi_seed(monkeypatch, tmp_path):
    sid, calls = _confirmed("u6", monkeypatch, tmp_path)
    client.post("/feedback", json={"session_id": sid, "track_id": "libtr_0", "verdict": "like"})
    client.post("/feedback", json={"session_id": sid, "track_id": "libtr_2", "verdict": "like"})
    body = client.post("/feedback", json={"session_id": sid, "track_id": "libtr_1", "verdict": "dislike"}).json()
    assert calls["similar"] == 2 and calls["multi"] == 0   # 每次 like 只用被点击歌曲做单种子相似
    ids = [c["track_id"] for c in body["cards"]]
    assert "sim_0" in ids
    assert len(ids) == orch.config.VISIBLE_N


def test_dislike_without_any_like_uses_backlog(monkeypatch, tmp_path):
    sid, calls = _confirmed("u4", monkeypatch, tmp_path)
    body = client.post("/feedback", json={"session_id": sid, "track_id": "libtr_0", "verdict": "dislike"}).json()
    assert calls["similar"] == 0                         # 没 liked 种子 → 不搜索
    ids = [c["track_id"] for c in body["cards"]]
    assert "libtr_0" not in ids                          # 被移除
    assert "libtr_5" in ids                              # 用 freeText backlog 补位
    assert len(ids) == orch.config.VISIBLE_N


def test_pool_reused_when_liked_set_unchanged(monkeypatch, tmp_path):
    sid, calls = _confirmed("u5", monkeypatch, tmp_path)
    client.post("/feedback", json={"session_id": sid, "track_id": "libtr_0", "verdict": "like"})
    client.post("/feedback", json={"session_id": sid, "track_id": "libtr_1", "verdict": "dislike"})
    client.post("/feedback", json={"session_id": sid, "track_id": "libtr_2", "verdict": "dislike"})
    assert calls["similar"] == 1  # liked 集合没变 → 候选池复用，不重复搜


def test_explain_similar_refill_uses_session_liked_seed(monkeypatch, tmp_path):
    sid, _ = _confirmed("similar_explain", monkeypatch, tmp_path)
    client.post("/feedback", json={"session_id": sid, "track_id": "libtr_0", "verdict": "like"})
    captured = {}

    def fake_build_explanation(profile_md, query_card, liked_track_tags, recommended_track_tags,
                               recommendation_meta, explanation_example=None, recommended_track=None):
        captured.update({
            "liked_track_tags": liked_track_tags,
            "recommended_track_tags": recommended_track_tags,
            "recommendation_meta": recommendation_meta,
            "explanation_example": explanation_example,
            "recommended_track": recommended_track,
        })
        return {"why_text": "Because it is close to the liked seed.", "evidence": []}

    monkeypatch.setattr(orch.cyanite, "model_tags", lambda cid, models: {"track": cid})
    monkeypatch.setattr(orch.explanation_builder, "build_explanation", fake_build_explanation)

    body = client.post("/explain", json={"session_id": sid, "track_id": "sim_0"}).json()

    assert body["why_text"].startswith("Because")
    assert captured["liked_track_tags"]["track"] == "libtr_0"
    assert captured["recommended_track_tags"]["track"] == "sim_0"
    assert captured["recommendation_meta"]["source"] == "similar"
    assert captured["recommendation_meta"]["source_liked_track"] == "libtr_0"
    assert captured["explanation_example"]["example_type"] == "session_source"
    assert captured["recommended_track"]["cyanite_id"] == "sim_0"


def test_explain_profile_semantic_refill_uses_profile_metadata(monkeypatch, tmp_path):
    sid, _ = _confirmed("profile_explain", monkeypatch, tmp_path)
    # anti_addiction 的语义回填用的是过往已建立的画像（来自之前已完成的轮），
    # 而记忆只在一轮结束时落，所以这里预置一份画像模拟老用户。
    (tmp_path / "profile_explain.memory.md").write_text(
        "# memory · profile_explain\n\n## 你的感觉\n你偏向 calm、warm 的感觉。\n",
        encoding="utf-8",
    )
    client.post(
        "/feedback",
        json={
            "session_id": sid,
            "track_id": "libtr_0",
            "verdict": "like",
            "mode": "anti_addiction",
        },
    )
    client.post(
        "/feedback",
        json={
            "session_id": sid,
            "track_id": "libtr_1",
            "verdict": "dislike",
            "mode": "anti_addiction",
        },
    )
    captured = {}

    def fake_build_explanation(profile_md, query_card, liked_track_tags, recommended_track_tags,
                               recommendation_meta, explanation_example=None, recommended_track=None):
        captured.update({
            "profile_md": profile_md,
            "liked_track_tags": liked_track_tags,
            "recommendation_meta": recommendation_meta,
            "explanation_example": explanation_example,
            "recommended_track": recommended_track,
        })
        return {"why_text": "Because it is close to your profile.", "evidence": []}

    monkeypatch.setattr(orch.cyanite, "model_tags", lambda cid, models: {"track": cid})
    monkeypatch.setattr(orch.explanation_builder, "build_explanation", fake_build_explanation)

    body = client.post("/explain", json={"session_id": sid, "track_id": "profile_0"}).json()

    assert body["why_text"].startswith("Because")
    assert captured["profile_md"].startswith("# memory")
    assert captured["liked_track_tags"] == {}
    assert captured["recommendation_meta"]["source"] == "profile_semantic"
    assert captured["recommendation_meta"]["ranking_basis"] == "profile_semantic_search"
    assert captured["recommendation_meta"]["profile_query"].startswith("# memory")
    assert captured["explanation_example"] is None
    assert captured["recommended_track"]["cyanite_id"] == "profile_0"


def test_explain_uses_historical_similar_intersection(monkeypatch, tmp_path):
    sid, calls = _confirmed("u7", monkeypatch, tmp_path)
    (tmp_path / "u7.evidence.md").write_text(
        "# evidence · u7\n\n## 反馈记录\n- 「old focus」→ liked hist_1   (2026-06-27T20:00:00)\n",
        encoding="utf-8",
    )
    (tmp_path / "u7.memory.md").write_text(
        "# memory · u7\n\nThe listener likes quiet, restrained focus tracks.\n",
        encoding="utf-8",
    )

    def fake_similar(cid, limit=20):
        calls["similar"] += 1
        assert cid == "libtr_0"
        return [{"cyanite_id": "hist_1", "score": 0.91}]

    captured = {}

    def fake_build_explanation(profile_md, query_card, liked_track_tags, recommended_track_tags,
                               recommendation_meta, explanation_example=None, recommended_track=None):
        captured.update({
            "profile_md": profile_md,
            "query_card": query_card,
            "liked_track_tags": liked_track_tags,
            "recommended_track_tags": recommended_track_tags,
            "recommendation_meta": recommendation_meta,
            "explanation_example": explanation_example,
            "recommended_track": recommended_track,
        })
        return {"why_text": "Because it connects to a previous liked track.", "evidence": []}

    monkeypatch.setattr(orch.cyanite, "find_similar", fake_similar)
    monkeypatch.setattr(orch.cyanite, "model_tags", lambda cid, models: {"track": cid, "models": models})
    monkeypatch.setattr(orch.explanation_builder, "build_explanation", fake_build_explanation)

    body = client.post("/explain", json={"session_id": sid, "track_id": "libtr_0"}).json()

    assert body["why_text"].startswith("Because")
    assert calls["similar"] == 1
    assert captured["profile_md"].startswith("# memory")
    assert captured["query_card"]["free_text_query"] == "test intent"
    assert captured["recommended_track_tags"]["track"] == "libtr_0"
    assert captured["liked_track_tags"]["track"] == "hist_1"
    assert captured["recommended_track"]["cyanite_id"] == "libtr_0"
    assert captured["explanation_example"] == {
        "track_id": "hist_1",
        "example_type": "historical_like",
        "similar_score": 0.91,
        "selection_basis": "historical_similarity",
        "title": "T",
        "artist": "A",
    }


def test_explain_uses_provided_user_likes_when_evidence_is_empty(monkeypatch, tmp_path):
    sid, calls = _confirmed("provided_user", monkeypatch, tmp_path)

    def fake_similar(cid, limit=20):
        calls["similar"] += 1
        return [{"cyanite_id": "provided_hist", "score": 0.93}]

    captured = {}

    def fake_build_explanation(profile_md, query_card, liked_track_tags, recommended_track_tags,
                               recommendation_meta, explanation_example=None, recommended_track=None):
        captured["explanation_example"] = explanation_example
        captured["liked_track_tags"] = liked_track_tags
        return {"why_text": "Because it connects to provided history.", "evidence": []}

    monkeypatch.setattr(orch.user_profiles, "liked_cyanite_ids", lambda u: ["provided_hist"])
    monkeypatch.setattr(orch.cyanite, "find_similar", fake_similar)
    monkeypatch.setattr(orch.cyanite, "model_tags", lambda cid, models: {"track": cid})
    monkeypatch.setattr(orch.explanation_builder, "build_explanation", fake_build_explanation)

    body = client.post("/explain", json={"session_id": sid, "track_id": "libtr_0"}).json()

    assert body["why_text"].startswith("Because")
    assert captured["liked_track_tags"]["track"] == "provided_hist"
    assert captured["explanation_example"]["track_id"] == "provided_hist"
    assert captured["explanation_example"]["similar_score"] == 0.93


def test_unknown_session_404(monkeypatch, tmp_path):
    _fake_seams(monkeypatch, tmp_path)
    assert client.post("/intent/confirm", json={"session_id": "nope"}).status_code == 404
