"""שלב 1: סריקת אתר הפניקס עם Playwright — Same-Domain BFS.

הרצה:
    python crawl.py

אסטרטגיה:
    מתחילים מ-START_URL ועוקבים אחרי כל הקישורים באותו דומיין (same-domain).
    MAX_DEPTH שולט כמה רמות עומק לסרוק (1 = רק קישורים ישירים מהדף הראשי).
    לא צריך INCLUDE_PATHS — הסריקה מגלה הכול אוטומטית.
    אין הגבלת קרדיטים — הכול מתבצע מקומית.
"""

import os
import json
import re
import asyncio
from datetime import date
from urllib.parse import urljoin, urlparse
from collections import deque

from dotenv import load_dotenv
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeout
from markdownify import markdownify as md2

load_dotenv()

START_URL  = os.getenv("START_URL", "https://www.fnx.co.il")
MAX_DEPTH  = int(os.getenv("MAX_DEPTH", "1"))
CONCURRENCY = int(os.getenv("CONCURRENCY", "5"))
MIN_CHARS  = 200          # עמודים קצרים מזה ידולגו
OUT        = os.path.join("data", "pages.json")

# דומיין בסיסי לסינון קישורים
_parsed    = urlparse(START_URL)
BASE_DOMAIN = _parsed.netloc.lstrip("www.")   # "fnx.co.il"

# קישורים שכדאי לדלג עליהם
SKIP_PATTERNS = re.compile(
    r"(login|portal|garages|doctors|dentists|\.pdf$|#|mailto:|tel:|javascript:)",
    re.IGNORECASE,
)


def same_domain(url: str) -> bool:
    h = urlparse(url).netloc.lstrip("www.")
    return h == BASE_DOMAIN or h.endswith("." + BASE_DOMAIN)


def normalise(url: str) -> str:
    """הסרת fragment ו-trailing slash כדי למנוע כפילויות."""
    p = urlparse(url)
    clean = p._replace(fragment="", query="").geturl()
    return clean.rstrip("/")


async def fetch_page(page, url: str) -> tuple[str, str, list[str]]:
    """מחזירה (title, markdown_text, [links])."""
    try:
        await page.goto(url, timeout=30_000, wait_until="domcontentloaded")
        # המתנה קצרה לתכנים דינמיים
        await page.wait_for_timeout(1_500)
    except PlaywrightTimeout:
        return "", "", []

    try:
        title = await page.title()

        # שליפת HTML של body בלבד
        html = await page.evaluate("document.body.innerHTML")
        text = md2(html, strip=["script", "style", "nav", "footer", "header"])

        # שליפת כל ה-href-ים
        hrefs = await page.evaluate("""
            () => Array.from(document.querySelectorAll('a[href]'))
                       .map(a => a.href)
        """)
    except Exception:
        # הדף ניווט שוב תוך כדי קריאה (redirect) — מדלגים
        return "", "", []
    links = []
    for h in hrefs:
        full = urljoin(url, h)
        n = normalise(full)
        if same_domain(n) and not SKIP_PATTERNS.search(n):
            links.append(n)

    return title, text, links


async def crawl_all() -> list[dict]:
    visited   = set()
    queue     = deque([(normalise(START_URL), 0)])  # (url, depth)
    pages_out = []

    sem = asyncio.Semaphore(CONCURRENCY)

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            locale="he-IL",
        )

        async def process(url: str, depth: int):
            async with sem:
                page = await context.new_page()
                try:
                    title, text, links = await fetch_page(page, url)
                finally:
                    await page.close()

            if len(text) >= MIN_CHARS:
                pages_out.append({
                    "url": url,
                    "title": title,
                    "markdown": text.strip(),
                    "scraped_at": str(date.today()),
                })
                print(f"  ✓ [{len(pages_out):>4}] (depth={depth}) {url}")
            else:
                print(f"  ✗ קצר מדי (depth={depth}) {url}")

            # הוספת קישורים חדשים לתור אם לא עברנו את max_depth
            if depth < MAX_DEPTH:
                for link in links:
                    if link not in visited:
                        visited.add(link)
                        queue.append((link, depth + 1))

        # BFS — מעבדים כמה עמודים במקביל
        start = normalise(START_URL)
        visited.add(start)

        while queue:
            # אוספים batch לפי CONCURRENCY
            batch = []
            while queue and len(batch) < CONCURRENCY:
                batch.append(queue.popleft())

            await asyncio.gather(*[process(u, d) for u, d in batch])

        await browser.close()

    return pages_out


if __name__ == "__main__":
    print(f"מתחילה לסרוק את {START_URL} (max_depth={MAX_DEPTH}, concurrency={CONCURRENCY})...")
    pages = asyncio.run(crawl_all())

    os.makedirs("data", exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(pages, f, ensure_ascii=False, indent=2)

    print(f"\n✅ נשמרו {len(pages)} עמודים ל-{OUT}")
