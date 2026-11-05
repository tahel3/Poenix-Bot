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
from playwright.async_api import async_playwright, Error as PlaywrightError
from markdownify import markdownify as md2
from bs4 import BeautifulSoup

load_dotenv()

START_URL  = os.getenv("START_URL", "https://www.fnx.co.il")
MAX_DEPTH  = int(os.getenv("MAX_DEPTH", "1"))
CONCURRENCY = int(os.getenv("CONCURRENCY", "5"))
MIN_CHARS  = 200          # עמודים קצרים מזה ידולגו
MIN_EXTRA_CHARS = 40      # מחרוזות קצרות מזה בנתוני Nuxt (כיתובים וכפתורים) ידולגו
OUT        = os.path.join("data", "pages.json")
PARTIAL_OUT = os.path.join("data", "pages.partial.json")
MIN_KEEP_RATIO = 0.8      # פחות מזה מהעמודים הקיימים נחשב לסריקה חלקית
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)

# דומיין בסיסי לסינון קישורים
_parsed    = urlparse(START_URL)
BASE_DOMAIN = _parsed.netloc.lstrip("www.")   # "fnx.co.il"

# קישורים שכדאי לדלג עליהם
SKIP_PATTERNS = re.compile(
    r"(login|portal|garages|doctors|dentists|\.(pdf|xlsx?|docx?|pptx?|csv|zip)$|#|mailto:|tel:|javascript:)",
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


# ה-HTML של הדף בלי מה שאינו תוכן. חייבים להסיר את התגים כאן: strip של markdownify
# מסיר רק את התג עצמו ומשאיר את התוכן שלו (כך קוד של סקריפטים נכנס בעבר לאינדקס).
CLEAN_BODY_JS = """
() => {
    const body = document.body.cloneNode(true);
    body.querySelectorAll(
        'script, style, noscript, template, svg, img, iframe, nav, footer, header'
    ).forEach(e => e.remove());
    return body.innerHTML;
}
"""

# חלק מתוכן האתר (מאמרים, תשובות נפתחות) נמצא רק בנתוני הדף של Nuxt ולא ב-DOM.
# אוספים מהם רק מחרוזות HTML בעברית.
NUXT_HTML_JS = """
() => {
    const found = new Set(), seen = new WeakSet();
    const walk = (v) => {
        if (typeof v === 'string') {
            if (/<[a-z][^>]*>/i.test(v) && /[א-ת]/.test(v)) found.add(v);
        } else if (v && typeof v === 'object' && !seen.has(v)) {
            seen.add(v);
            Object.values(v).forEach(walk);
        }
    };
    walk(window.__NUXT__);
    return [...found];
}
"""


def to_markdown(html: str) -> str:
    return md2(html, heading_style="ATX", strip=["a"])


def plain_text(html: str) -> str:
    return " ".join(BeautifulSoup(html, "html.parser").get_text(" ").split())


def build_markdown(body_html: str, nuxt_html: list[str]) -> str:
    """טקסט הדף, ואחריו תוכן מנתוני Nuxt שלא מופיע בדף עצמו."""
    page_text = plain_text(body_html)
    extra = []
    for html in nuxt_html:
        text = plain_text(html)
        if len(text) >= MIN_EXTRA_CHARS and text not in page_text:
            extra.append(to_markdown(html).strip())
    markdown = to_markdown(body_html)
    if extra:
        markdown += "\n\n## תוכן נוסף מהעמוד\n\n" + "\n\n".join(extra)
    return markdown


async def fetch_page(page, url: str) -> tuple[str, str, list[str]]:
    """מחזירה (title, markdown_text, [links])."""
    try:
        response = await page.goto(url, timeout=30_000, wait_until="domcontentloaded")
        # דף שגיאה או חסימה הוא לא תוכן של האתר
        if response is None or not response.ok:
            status = response.status if response else "?"
            print(f"  ✗ סטטוס {status} {url}")
            return "", "", []
        # המתנה קצרה לתכנים דינמיים
        await page.wait_for_timeout(1_500)
    except PlaywrightError as e:
        # timeout, הורדת קובץ במקום דף וכו': מדלגים על העמוד וממשיכים בסריקה
        print(f"  ✗ שגיאה {url}: {str(e).splitlines()[0]}")
        return "", "", []

    try:
        title = await page.title()

        body_html = await page.evaluate(CLEAN_BODY_JS)
        nuxt_html = await page.evaluate(NUXT_HTML_JS)
        text = build_markdown(body_html, nuxt_html)

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
            user_agent=USER_AGENT,
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


def save_pages(pages: list[dict]) -> bool:
    """שומרת ל-OUT, אלא אם הסריקה החזירה הרבה פחות עמודים ממה שכבר שמור (למשל בגלל חסימה)."""
    os.makedirs(os.path.dirname(OUT), exist_ok=True)

    previous = 0
    if os.path.exists(OUT):
        with open(OUT, encoding="utf-8") as f:
            previous = len(json.load(f))

    too_few = len(pages) < previous * MIN_KEEP_RATIO
    path = PARTIAL_OUT if too_few else OUT
    with open(path, "w", encoding="utf-8") as f:
        json.dump(pages, f, ensure_ascii=False, indent=2)

    if too_few:
        print(f"\n⚠️  נסרקו רק {len(pages)} עמודים, לעומת {previous} ב-{OUT}. הקובץ הקיים לא נדרס.")
        print(f"   התוצאה נשמרה ל-{PARTIAL_OUT}. אם היא תקינה, החליפי ידנית את {OUT} בקובץ הזה.")
        return False
    print(f"\n✅ נשמרו {len(pages)} עמודים ל-{OUT}")
    return True


if __name__ == "__main__":
    print(f"מתחילה לסרוק את {START_URL} (max_depth={MAX_DEPTH}, concurrency={CONCURRENCY})...")
    pages = asyncio.run(crawl_all())
    if not save_pages(pages):
        raise SystemExit(1)
