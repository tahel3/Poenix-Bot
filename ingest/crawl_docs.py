"""שלב 1ב: הורדת המסמכים שברשימה documents.json והוצאת הטקסט מהם.

הרצה (מתוך תיקיית ingest):
    python crawl_docs.py --limit 5    # בדיקה על 5 מסמכים, בלי לגעת בפלט הקיים
    python crawl_docs.py              # כל הרשימה

התוצאה נשמרת ל-data/doc_pages.json באותו מבנה של pages.json, ו-build_index.py קורא אותה.
קובצי PDF נשמרים ב-data/docs, כך שהרצה חוזרת לא מורידה אותם שוב.
מסמך סרוק או עם טקסט עברי הפוך לא נכנס לאינדקס, ומופיע בדוח בסוף הריצה.
"""
import os
import re
import sys
import json
import asyncio
import hashlib
from datetime import date
from io import BytesIO

from playwright.async_api import async_playwright, Error as PlaywrightError
from pypdf import PdfReader

from crawl import USER_AGENT

LIST_FILE = "documents.json"
CACHE_DIR = os.path.join("data", "docs")
OUT = os.path.join("data", "doc_pages.json")
SAMPLE_OUT = os.path.join("data", "doc_pages.sample.json")
DELAY_SECONDS = 1.0       # הפסקה בין הורדות, כדי לא להעמיס על האתר
MIN_HEBREW_LETTERS = 200  # פחות מזה: כנראה מסמך סרוק
WORDS_PER_CHUNK = 520     # MAX_WORDS פחות החפיפה ב-build_index.py
SECONDS_PER_CHUNK = 12    # הקצב ב-build_index.py
FINAL_LETTERS = "ךםןףץ"


def extract_text(pdf_bytes: bytes) -> str:
    reader = PdfReader(BytesIO(pdf_bytes))
    pages = [(page.extract_text() or "") for page in reader.pages]
    text = "\n".join(pages).replace("\x00", "")  # Postgres לא מקבל תווי NUL
    lines = (" ".join(line.split()) for line in text.splitlines())
    return "\n".join(line for line in lines if line)


def problem_with(text: str) -> str | None:
    """מחזירה את סיבת הפסילה של הטקסט, או None אם הוא תקין."""
    if sum("א" <= c <= "ת" for c in text) < MIN_HEBREW_LETTERS:
        return "מעט טקסט בעברית (כנראה סרוק)"
    # אות סופית שנמצאת בתחילת מילים ולא בסופן מעידה על טקסט שנשמר הפוך
    words = re.findall(r"[א-ת]{2,}", text)
    at_end = sum(w[-1] in FINAL_LETTERS for w in words)
    at_start = sum(w[0] in FINAL_LETTERS for w in words)
    if at_start > at_end:
        return "טקסט עברי הפוך"
    return None


async def get_pdf(context, url: str) -> bytes:
    """מחזירה את תוכן ה-PDF מהמטמון או מהאתר. זורקת ValueError אם ההורדה לא תקינה."""
    path = os.path.join(CACHE_DIR, hashlib.sha256(url.encode()).hexdigest()[:16] + ".pdf")
    if os.path.exists(path):
        with open(path, "rb") as f:
            return f.read()

    response = await context.request.get(url, timeout=60_000)
    if not response.ok:
        raise ValueError(f"סטטוס {response.status}")
    body = await response.body()
    if not body.startswith(b"%PDF"):
        raise ValueError("הקובץ שהתקבל אינו PDF")

    os.makedirs(CACHE_DIR, exist_ok=True)
    with open(path, "wb") as f:
        f.write(body)
    await asyncio.sleep(DELAY_SECONDS)
    return body


async def crawl_docs(docs: list[dict]) -> tuple[list[dict], list[tuple[str, str]]]:
    pages, skipped = [], []
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        context = await browser.new_context(user_agent=USER_AGENT, locale="he-IL")
        for i, doc in enumerate(docs, 1):
            url = doc["url"]
            try:
                text = extract_text(await get_pdf(context, url))
                reason = problem_with(text)
            except (PlaywrightError, ValueError) as e:
                reason = str(e).splitlines()[0]
            except Exception as e:  # קובץ PDF פגום
                reason = f"לא ניתן לקרוא את הקובץ: {type(e).__name__}"

            if reason:
                skipped.append((url, reason))
                print(f"  ✗ [{i}/{len(docs)}] {reason}: {doc['title']}")
                continue
            pages.append({
                "url": url,
                "title": doc["title"],
                "markdown": text,
                "scraped_at": str(date.today()),
            })
            print(f"  ✓ [{i}/{len(docs)}] {len(text.split())} מילים: {doc['title']}")
        await browser.close()
    return pages, skipped


def parse_limit() -> int | None:
    if "--limit" in sys.argv:
        return int(sys.argv[sys.argv.index("--limit") + 1])
    return None


if __name__ == "__main__":
    with open(LIST_FILE, encoding="utf-8") as f:
        docs = json.load(f)

    limit = parse_limit()
    if limit is not None:
        docs = docs[:limit]

    pages, skipped = asyncio.run(crawl_docs(docs))

    path = OUT if limit is None else SAMPLE_OUT
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(pages, f, ensure_ascii=False, indent=2)

    words = sum(len(p["markdown"].split()) for p in pages)
    chunks = words // WORDS_PER_CHUNK + len(pages)
    hours = chunks * SECONDS_PER_CHUNK / 3600
    print(f"\n✅ נשמרו {len(pages)} מתוך {len(docs)} מסמכים ל-{path}")
    print(f"   הערכה: כ-{chunks} קטעים, שיוסיפו כ-{hours:.1f} שעות לבניית האינדקס")
    if skipped:
        print(f"\n⚠️  {len(skipped)} מסמכים לא נכנסו:")
        for url, reason in skipped:
            print(f"   {reason}: {url}")
