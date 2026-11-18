"use client";
import { useEffect, useRef, useState } from "react";
import { STRINGS, type Lang } from "@/lib/i18n";

type Chunk = { url: string; score: number; text: string };
type Msg = {
  role: "user" | "assistant";
  content: string;
  sources?: string[];
  score?: number;
  found?: boolean;
  chunks?: Chunk[];
};

// הציון מודד קרבה בנושא בין השאלה לקטע, לא אם התשובה נמצאת בו. לכן בסירוב אין תג ירוק.
function matchLabel(score: number, found: boolean | undefined, lang: Lang) {
  const t = STRINGS[lang];
  if (!found) return { cls: "low", text: t.notFoundBadge };
  if (score >= 0.72) return { cls: "high", text: t.high };
  if (score >= 0.55) return { cls: "mid", text: t.mid };
  return { cls: "low", text: t.low };
}

export default function Home() {
  const [messages, setMessages] = useState<Msg[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [debug, setDebug] = useState(false);
  const [lang, setLang] = useState<Lang>("he");
  const endRef = useRef<HTMLDivElement>(null);
  const t = STRINGS[lang];

  // Restore the saved language (e.g. ?lang=en from a portfolio link, or the last choice)
  useEffect(() => {
    const fromUrl = new URLSearchParams(window.location.search).get("lang");
    let saved: string | null = null;
    try { saved = localStorage.getItem("lang"); } catch {}
    const initial = fromUrl === "en" || fromUrl === "he" ? fromUrl : saved;
    if (initial === "en" || initial === "he") setLang(initial);
  }, []);

  useEffect(() => {
    document.documentElement.lang = lang;
    document.documentElement.dir = STRINGS[lang].dir;
    try { localStorage.setItem("lang", lang); } catch {}
  }, [lang]);

  function toggleLang() {
    setLang((l) => (l === "he" ? "en" : "he"));
    setMessages([]); // answers are language-specific, start fresh
  }

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
        body: JSON.stringify({ question, history, lang }),
      });
      const data = await res.json();
      setMessages((m) => [
        ...m,
        { role: "assistant", content: data.answer, sources: data.sources, score: data.score, found: data.found, chunks: data.chunks },
      ]);
    } catch {
      setMessages((m) => [...m, { role: "assistant", content: t.error }]);
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
          <h1>{t.title}</h1>
          <div className="tagline">{t.tagline}</div>
        </div>
        <button type="button" className="lang-toggle" onClick={toggleLang} aria-label={t.toggleAria}>
          {t.toggleLabel}
        </button>
      </div>
      <div className="sub">{t.sub}</div>

      {messages.length === 0 && (
        <div className="examples">
          {t.examples.map((e) => (
            <button key={e} className="chip" onClick={() => send(e)}>
              {e}
            </button>
          ))}
        </div>
      )}

      <div className="tools">
        <label>
          <input type="checkbox" checked={debug} onChange={(e) => setDebug(e.target.checked)} /> {t.showChunks}
        </label>
        {messages.length > 0 && (
          <button className="link" onClick={() => setMessages([])}>
            {t.newChat}
          </button>
        )}
      </div>

      <div className="chat">
        {messages.map((m, i) => (
          <div key={i} className={`msg ${m.role === "user" ? "user" : "bot"}`}>
            {m.content}
            {m.role === "assistant" && m.score !== undefined && (
              <div className="meta">
                <span className={`badge ${matchLabel(m.score, m.found, lang).cls}`}>{matchLabel(m.score, m.found, lang).text}</span>
                {m.found && m.sources && m.sources.length > 0 && (
                  <div>
                    <b>{t.source}</b>
                    {m.sources.map((u) => (
                      <a key={u} href={u} target="_blank" rel="noreferrer">
                        {u}
                      </a>
                    ))}
                  </div>
                )}
                {debug && m.chunks && (
                  <details open>
                    <summary>{t.chunksFound}</summary>
                    {m.chunks.map((c, j) => (
                      <div key={j} className="chunk">
                        <b>{t.match} {c.score.toFixed(2)}</b> ·{" "}
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
        <input value={input} onChange={(e) => setInput(e.target.value)} placeholder={t.placeholder} maxLength={500} />
        <button className="send" disabled={loading || !input.trim()} aria-label={t.send}>
          <svg viewBox="0 0 24 24" width="18" height="18" fill="none" xmlns="http://www.w3.org/2000/svg">
            <path d="M20 12H5M12 5L5 12L12 19" stroke="white" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
        </button>
      </form>
    </div>
    </div>
  );
}
