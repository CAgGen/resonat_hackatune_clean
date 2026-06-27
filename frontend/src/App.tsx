import { useState } from "react";
import { intent, type QueryCard } from "./api";

// 最小连通验证：输入一句话 → /intent → 看到 Query Card。后续按 PRD 填确认门/反馈。
export default function App() {
  const [text, setText] = useState("背叛");
  const [card, setCard] = useState<QueryCard | null>(null);
  const [err, setErr] = useState("");

  async function go() {
    setErr("");
    try {
      setCard(await intent(text));
    } catch (e) {
      setErr(String(e));
    }
  }

  return (
    <main style={{ maxWidth: 640, margin: "3rem auto", fontFamily: "system-ui" }}>
      <h1>Cochlea</h1>
      <input value={text} onChange={(e) => setText(e.target.value)} style={{ width: "70%" }} />
      <button onClick={go} style={{ marginLeft: 8 }}>意图编译</button>
      {err && <p style={{ color: "crimson" }}>{err}</p>}
      {card && <pre style={{ background: "#f4f4f4", padding: 12 }}>{JSON.stringify(card, null, 2)}</pre>}
    </main>
  );
}
