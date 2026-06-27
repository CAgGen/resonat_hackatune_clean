"""编排框架自检。monkeypatch 三个接缝（cyanite / intent_compiler / memory），离线跑主循环。
新逻辑：like 只记 liked 种子（不搜索）；similarById 只由 dislike 触发，种子是 liked 曲。
run: uv run pytest -v
"""
from fastapi.testclient import TestClient

import app
import orchestrator as orch

client = TestClient(app.app)

SEARCH = [{"cyanite_id": f"libtr_{i}", "score": 1.0 - i / 10} for i in range(8)]   # 8 首
SIMILAR = [{"cyanite_id": f"sim_{i}", "score": 0.9 - i / 10} for i in range(3)]    # 单种子相似
MULTI = [{"cyanite_id": f"multi_{i}", "score": 0.95 - i / 10} for i in range(3)]   # 多种子相似


def _fake_seams(monkeypatch, tmp_path):
    """返回计数器 dict，记录单种子 / 多种子相似各被调了几次。"""
    calls = {"similar": 0, "multi": 0}

    def fake_similar(cid, limit=20):
        calls["similar"] += 1
        return SIMILAR

    def fake_multi(cids, limit=20):
        calls["multi"] += 1
        return MULTI

    monkeypatch.setattr(orch.cyanite, "search_by_prompt", lambda q, limit=20: SEARCH)
    monkeypatch.setattr(orch.cyanite, "find_similar", fake_similar)
    monkeypatch.setattr(orch.cyanite, "find_similar_multi", fake_multi)
    monkeypatch.setattr(orch.cyanite, "display",
                        lambda cid: {"track_id": cid, "cyanite_id": cid, "title": "T", "artist": "A"})
    monkeypatch.setattr(orch.memory, "_ev_path", lambda u: tmp_path / f"{u}.evidence.md")
    monkeypatch.setattr(orch.memory, "_mem_path", lambda u: tmp_path / f"{u}.memory.md")
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
                        lambda q, limit=20: hit.update(n=hit["n"] + 1) or SEARCH)
    sid = client.post("/intent", json={"text": "dark betrayal", "user_id": "u1"}).json()["session_id"]
    client.post("/intent/follow-up", json={"session_id": sid, "text": "more restrained"})
    assert hit["n"] == 0  # 确认门：确认前不检索


def test_confirm_fills_visible_and_backlog(monkeypatch, tmp_path):
    sid, _ = _confirmed("u1", monkeypatch, tmp_path)
    body = client.post("/intent/confirm", json={"session_id": sid}).json()
    assert len(body["cards"]) == orch.config.VISIBLE_N
    assert len(orch.SESSIONS[sid]["free_text_backlog"]) == len(SEARCH) - orch.config.VISIBLE_N


def test_like_records_seed_without_searching(monkeypatch, tmp_path):
    sid, calls = _confirmed("u2", monkeypatch, tmp_path)
    before = [c["track_id"] for c in orch.SESSIONS[sid]["visible_cards"]]
    body = client.post("/feedback", json={"session_id": sid, "track_id": "libtr_0", "verdict": "like"}).json()
    assert calls["similar"] == 0                       # like 不触发搜索
    assert body["candidate_pool_size"] == 0            # 候选池仍空
    assert orch.SESSIONS[sid]["liked_tracks"] == ["libtr_0"]
    assert [c["track_id"] for c in body["cards"]] == before  # 当前列表不变
    assert (tmp_path / "u2.evidence.md").read_text(encoding="utf-8").count("\n- ") == 1


def test_dislike_with_one_like_uses_single_seed(monkeypatch, tmp_path):
    sid, calls = _confirmed("u3", monkeypatch, tmp_path)
    client.post("/feedback", json={"session_id": sid, "track_id": "libtr_0", "verdict": "like"})
    assert calls["similar"] == 0 and calls["multi"] == 0   # like 后仍未搜索
    body = client.post("/feedback", json={"session_id": sid, "track_id": "libtr_1", "verdict": "dislike"}).json()
    assert calls["similar"] == 1 and calls["multi"] == 0   # 1 个 liked → 单种子
    ids = [c["track_id"] for c in body["cards"]]
    assert "libtr_1" not in ids                            # 被移除
    assert "sim_0" in ids                                  # 最高 similar_score 回填
    assert len(ids) == orch.config.VISIBLE_N               # 槽位数不变


def test_dislike_with_two_likes_uses_multi_seed(monkeypatch, tmp_path):
    sid, calls = _confirmed("u6", monkeypatch, tmp_path)
    client.post("/feedback", json={"session_id": sid, "track_id": "libtr_0", "verdict": "like"})
    client.post("/feedback", json={"session_id": sid, "track_id": "libtr_2", "verdict": "like"})
    body = client.post("/feedback", json={"session_id": sid, "track_id": "libtr_1", "verdict": "dislike"}).json()
    assert calls["multi"] == 1 and calls["similar"] == 0   # 2 个 liked → 多种子 multi
    ids = [c["track_id"] for c in body["cards"]]
    assert "multi_0" in ids                                # multi 结果回填
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


def test_unknown_session_404(monkeypatch, tmp_path):
    _fake_seams(monkeypatch, tmp_path)
    assert client.post("/intent/confirm", json={"session_id": "nope"}).status_code == 404
