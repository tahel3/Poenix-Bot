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

// הציון מודד קרבה בנושא בין השאלה לקטע, לא אם התשובה נמצאת בו. לכן בסירוב אין תג ירוק.
function matchLabel(score: number, found?: boolean) {
  if (!found) return { cls: "low", text: "🔴 לא נמצאה תשובה בקטעים מהאתר" };
  if (score >= 0.72) return { cls: "high", text: "🟢 נמצאו קטעים קרובים מאוד לשאלה" };
  if (score >= 0.55) return { cls: "mid", text: "🟡 נמצאו קטעים קרובים לשאלה" };
  return { cls: "low", text: "🔴 נמצאו קטעים רחוקים מהשאלה" };
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
    <div className="page">
    <div className="wrap">
      <div className="header">
        <div className="logo">
          <svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
            <path
              d="M12 2c1.2 2.2 3 3.6 3 6.2 0 1.7-1.3 3-3 3s-3-1.3-3-3c0 0-2 2.3-2 5.3C7 16.9 9.2 19 12 19s5-2.1 5-5.5c0-4.5-3-7-5-11.5z"
              fill="white"
            />
          </svg>
        </div>
        <div className="header-text">
          <h1>הפניקס · העוזר הדיגיטלי</h1>
          <div className="tagline">בוט שאפשר להאמין לו</div>
        </div>
      </div>
      <div className="sub">יש לכם שאלה על האתר שלנו? אדע לענות לכם תשובות אמינות, כולל מקור!</div>

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
                <span className={`badge ${matchLabel(m.score, m.found).cls}`}>{matchLabel(m.score, m.found).text}</span>
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
        {loading && (
          <div className="msg bot">
            <span className="typing">
              <span />
              <span />
              <span />
            </span>
          </div>
        )}
        <div ref={endRef} />
      </div>

      <form
        onSubmit={(e) => {
          e.preventDefault();
          send(input);
        }}
      >
        <input value={input} onChange={(e) => setInput(e.target.value)} placeholder="שאלי אותי משהו על הפניקס..." maxLength={500} />
        <button className="send" disabled={loading || !input.trim()} aria-label="שלח">
          <svg viewBox="0 0 24 24" width="18" height="18" fill="none" xmlns="http://www.w3.org/2000/svg">
            <path d="M20 12H5M12 5L5 12L12 19" stroke="white" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
        </button>
      </form>
    </div>
    </div>
  );
}
