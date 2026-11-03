"use client";
import { useEffect, useRef, useState } from "react";

type Chunk = { url: string; score: number; text: string };
type Msg = {
  role: "user" | "assistant";
  content: string;
  sources?: string[];
  score?: number;
  found?: boolean;
  chunks?: Chunk[];
};

const EXAMPLES = [
  "יש לי נזילה בבית, איך אני מגישה תביעה?",
  "ותוך כמה זמן מקבלים תשובה?",
  "האם הפוליסה שלי מכסה את זה?",
  "מה מזג האוויר מחר?",
];

function matchLabel(score: number) {
  if (score >= 0.72) return { cls: "high", text: "🟢 התאמה לאתר: גבוהה" };
  if (score >= 0.55) return { cls: "mid", text: "🟡 התאמה לאתר: בינונית" };
  return { cls: "low", text: "🔴 התאמה לאתר: נמוכה" };
}

export default function Home() {
  const [messages, setMessages] = useState<Msg[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [debug, setDebug] = useState(false);
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  async function send(text: string) {
    const question = text.trim();
    if (!question || loading) return;
    const history = messages.map((m) => ({ role: m.role, content: m.content }));
    setMessages((m) => [...m, { role: "user", content: question }]);
    setInput("");
    setLoading(true);
    try {
      const res = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question, history }),
      });
      const data = await res.json();
      setMessages((m) => [
        ...m,
        { role: "assistant", content: data.answer, sources: data.sources, score: data.score, found: data.found, chunks: data.chunks },
      ]);
    } catch {
      setMessages((m) => [...m, { role: "assistant", content: "אירעה תקלה זמנית, נסי שוב בעוד רגע." }]);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="wrap">
      <h1>🔥 הבוט שיודע את האתר של הפניקס</h1>
      <div className="sub">עונה אך ורק מתוך המידע שבאתר, עם מקור לכל תשובה. אם זה לא כתוב באתר - הוא יגיד.</div>

      {messages.length === 0 && (
        <div className="examples">
          {EXAMPLES.map((e) => (
            <button key={e} className="chip" onClick={() => send(e)}>
              {e}
            </button>
          ))}
        </div>
      )}

      <div className="tools">
        <label>
          <input type="checkbox" checked={debug} onChange={(e) => setDebug(e.target.checked)} /> הצג את הקטעים שנמצאו באתר
        </label>
        {messages.length > 0 && (
          <button className="link" onClick={() => setMessages([])}>
            שיחה חדשה
          </button>
        )}
      </div>

      <div className="chat">
        {messages.map((m, i) => (
          <div key={i} className={`msg ${m.role === "user" ? "user" : "bot"}`}>
            {m.content}
            {m.role === "assistant" && m.score !== undefined && (
              <div className="meta">
                <span className={`badge ${matchLabel(m.score).cls}`}>{matchLabel(m.score).text}</span>
                {m.found && m.sources && m.sources.length > 0 && (
                  <div>
                    <b>המקור:</b>
                    {m.sources.map((u) => (
                      <a key={u} href={u} target="_blank" rel="noreferrer">
                        {u}
                      </a>
                    ))}
                  </div>
                )}
                {debug && m.chunks && (
                  <details open>
                    <summary>הקטעים שנמצאו</summary>
                    {m.chunks.map((c, j) => (
                      <div key={j} className="chunk">
                        <b>התאמה {c.score.toFixed(2)}</b> ·{" "}
                        <a href={c.url} target="_blank" rel="noreferrer">
                          {c.url}
                        </a>
                        <div>{c.text}</div>
                      </div>
                    ))}
                  </details>
                )}
              </div>
            )}
          </div>
        ))}
        {loading && <div className="msg bot">מחפש באתר...</div>}
        <div ref={endRef} />
      </div>

      <form
        onSubmit={(e) => {
          e.preventDefault();
          send(input);
        }}
      >
        <input value={input} onChange={(e) => setInput(e.target.value)} placeholder="שאלי אותי משהו על הפניקס..." maxLength={500} />
        <button className="send" disabled={loading || !input.trim()}>
          שלח
        </button>
      </form>
    </div>
  );
}
