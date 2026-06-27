"""编排框架自检。monkeypatch 三个接缝（cyanite / intent_compiler / memory），离线跑主循环。
run: uv run pytest -v
"""
from fastapi.testclient import TestClient

import app
import orchestrator as orch

client = TestClient(app.app)

SEARCH = [{"cyanite_id": f"libtr_{i}", "score": 1.0 - i / 10} for i in range(8)]   # 8 首
SIMILAR = [{"cyanite_id": f"sim_{i}", "score": 0.9 - i / 10} for i in range(3)]    # 3 首相似


def _fake_seams(monkeypatch, tmp_path):
    monkeypatch.setattr(orch.cyanite, "search_by_prompt", lambda q, limit=20: SEARCH)
    monkeypatch.setattr(orch.cyanite, "find_similar", lambda cid, limit=20: SIMILAR)
    monkeypatch.setattr(orch.cyanite, "display",
                        lambda cid: {"track_id": cid, "cyanite_id": cid, "title": "T", "artist": "A"})
    monkeypatch.setattr(orch.memory, "MEM_DIR", tmp_path)
    monkeypatch.setattr(orch.memory, "_ev_path", lambda u: tmp_path / f"{u}.evidence.md")
    monkeypatch.setattr(orch.memory, "_mem_path", lambda u: tmp_path / f"{u}.memory.md")


def test_intent_does_not_search_until_confirm(monkeypatch, tmp_path):
    hit = {"n": 0}
    _fake_seams(monkeypatch, tmp_path)
    monkeypatch.setattr(orch.cyanite, "search_by_prompt",
                        lambda q, limit=20: hit.update(n=hit["n"] + 1) or SEARCH)
    sid = client.post("/intent", json={"text": "dark betrayal", "user_id": "u1"}).json()["session_id"]
    client.post("/intent/follow-up", json={"session_id": sid, "text": "more restrained"})
    assert hit["n"] == 0  # 确认门：确认前不检索


def test_confirm_fills_visible_and_backlog(monkeypatch, tmp_path):
    _fake_seams(monkeypatch, tmp_path)
    sid = client.post("/intent", json={"text": "x", "user_id": "u1"}).json()["session_id"]
    body = client.post("/intent/confirm", json={"session_id": sid}).json()
    assert len(body["cards"]) == orch.config.VISIBLE_N
    assert len(orch.SESSIONS[sid]["free_text_backlog"]) == len(SEARCH) - orch.config.VISIBLE_N


def test_like_fills_pool_keeps_visible_and_writes_memory(monkeypatch, tmp_path):
    _fake_seams(monkeypatch, tmp_path)
    sid = client.post("/intent", json={"text": "dark", "user_id": "u2"}).json()["session_id"]
    client.post("/intent/confirm", json={"session_id": sid})
    before = [c["track_id"] for c in orch.SESSIONS[sid]["visible_cards"]]
    body = client.post("/feedback", json={"session_id": sid, "track_id": "libtr_0", "verdict": "like"}).json()
    assert body["candidate_pool_size"] == len(SIMILAR)
    assert [c["track_id"] for c in body["cards"]] == before  # like 不冲当前列表
    assert (tmp_path / "u2.evidence.md").read_text(encoding="utf-8").count("\n- ") == 1


def test_dislike_removes_and_backfills_highest_similar(monkeypatch, tmp_path):
    _fake_seams(monkeypatch, tmp_path)
    sid = client.post("/intent", json={"text": "x", "user_id": "u3"}).json()["session_id"]
    client.post("/intent/confirm", json={"session_id": sid})
    client.post("/feedback", json={"session_id": sid, "track_id": "libtr_0", "verdict": "like"})
    body = client.post("/feedback", json={"session_id": sid, "track_id": "libtr_1", "verdict": "dislike"}).json()
    ids = [c["track_id"] for c in body["cards"]]
    assert "libtr_1" not in ids                  # 被移除
    assert "sim_0" in ids                         # 最高 similar_score 回填
    assert len(ids) == orch.config.VISIBLE_N      # 槽位数不变


def test_unknown_session_404(monkeypatch, tmp_path):
    _fake_seams(monkeypatch, tmp_path)
    assert client.post("/intent/confirm", json={"session_id": "nope"}).status_code == 404
