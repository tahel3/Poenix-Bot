"""שלב 2: חיתוך העמודים לקטעים, הטמעה (embeddings) ושמירה במסד הוקטורי ב-Supabase.

הרצה (מתוך תיקיית ingest):  python build_index.py
קורא את data/pages.json, מוחק את הקטעים הישנים בטבלה chunks ומעלה את החדשים.
(קודם מריצים פעם אחת את supabase/setup.sql ב-Supabase.)

מודל ה-embedding: gemini-embedding-001 — זהה למה שמשמש ב-web/lib/rag.ts לחיפוש.
"""
import os
import re
import json
import math
import time
from google import genai
from supabase import create_client
from dotenv import load_dotenv

load_dotenv()

EMBED_MODEL = os.getenv("EMBED_MODEL", "gemini-embedding-001")
DIMS = 768           # חייב להיות זהה ל-setup.sql ול-web/lib/rag.ts
MAX_WORDS = 600      # גודל קטע מקסימלי
OVERLAP_WORDS = 80   # חפיפה בין קטעים רצופים
BATCH = 1            # gemini free tier: 5 req/min → 1 קטע כל 12 שניות

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
db = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_SERVICE_KEY"))


def split_sections(markdown):
    sections, title, buf = [], "", []
    for line in markdown.splitlines():
        if re.match(r"^#{1,3}\s", line):
            if buf:
                sections.append((title, "\n".join(buf).strip()))
            title, buf = line.lstrip("# ").strip(), []
        else:
            buf.append(line)
    if buf:
        sections.append((title, "\n".join(buf).strip()))
    return [(t, b) for t, b in sections if len(b) > 80]


def split_long(text):
    words = text.split()
    if len(words) <= MAX_WORDS:
        return [text]
    parts, i = [], 0
    while i < len(words):
        parts.append(" ".join(words[i:i + MAX_WORDS]))
        i += MAX_WORDS - OVERLAP_WORDS
    return parts


def make_chunks(pages):
    chunks = []
    for p in pages:
        for section, body in split_sections(p["markdown"]):
            for part in split_long(body):
                text = f"{p['title']} | {section}\n{part}".strip()
                chunks.append({"content": text, "url": p["url"], "title": p["title"],
                               "section": section, "scraped_at": p["scraped_at"]})
    return chunks


def normalize(v):
    n = math.sqrt(sum(x * x for x in v)) or 1.0
    return [round(x / n, 6) for x in v]


def embed(texts):
    for attempt in range(6):
        try:
            res = client.models.embed_content(
                model=EMBED_MODEL,
                contents=texts,
                config={"task_type": "RETRIEVAL_DOCUMENT", "output_dimensionality": DIMS},
            )
            return [normalize(e.values) for e in res.embeddings]
        except Exception as e:
            wait = 2 ** attempt * 3
            print(f"  שגיאה ({str(e)[:80]}), מנסה שוב בעוד {wait} שניות")
            time.sleep(wait)
    raise RuntimeError("ההטמעה נכשלה שוב ושוב")


if __name__ == "__main__":
    with open(os.path.join("data", "pages.json"), encoding="utf-8") as f:
        pages = json.load(f)
    chunks = make_chunks(pages)
    print(f"{len(pages)} עמודים -> {len(chunks)} קטעים")

    # בדיקה כמה כבר הועלו — אם יקרוס נמשיך מאיפה שעצרנו
    existing = db.table("chunks").select("id", count="exact").execute()
    start_from = existing.count or 0
    if start_from > 0:
        print(f"  ממשיכה מקטע {start_from} (כבר הועלו)")
    else:
        db.table("chunks").delete().neq("id", 0).execute()
        print("  הטבלה נוקתה, מתחילה מהתחלה")

    for i in range(start_from, len(chunks), BATCH):
        batch = chunks[i:i + BATCH]
        for c, v in zip(batch, embed([c["content"] for c in batch])):
            c["embedding"] = v
        db.table("chunks").insert(batch).execute()
        print(f"  הועלו {min(i + BATCH, len(chunks))}/{len(chunks)}")
        time.sleep(12)

    print("✅ המסד הוקטורי מוכן. אפשר לבדוק ב-Supabase: Table Editor -> chunks")
