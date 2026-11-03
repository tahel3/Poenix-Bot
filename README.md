# בוט הפניקס: RAG שעונה רק מתוך האתר

בוט שעונה על שאלות לקוחות מתוך תוכן אתר הפניקס בלבד, עם מקור לכל תשובה, ואומר "זה לא כתוב באתר" כשאין מידע.

## ארכיטקטורה
- **`ingest/` (Python, רץ פעם אחת אצלך במחשב)**
  - `crawl.py`: Firecrawl סורק עמודים ציבוריים ל-Markdown, נשמר עם כתובת ותאריך איסוף.
  - `build_index.py`: חיתוך לפי כותרות (עד ~350 מילים, חפיפה 50), כותרת העמוד בראש כל קטע, הטמעות Gemini, והעלאה למסד הוקטורי ב-Supabase.
  - `eval.py`: מריץ שאלות מול ה-API ומודד דיוק והמצאות.
- **`supabase/setup.sql`**: תוסף pgvector, טבלת `chunks`, אינדקסים (HNSW + GIN), RLS, ופונקציית החיפוש ההיברידי `match_chunks`.
- **`web/` (Next.js + TypeScript, רץ ב-Vercel)**
  - `lib/rag.ts`: הטמעת השאלה, חיפוש היברידי (וקטורי + מילות מפתח, מאוחדים ב-RRF) מ-Supabase, סף התאמה (מתחתיו אין קריאה למודל), Gemini Flash עם הנחיה "ענה רק מהקטעים". המקורות מוצמדים בקוד, לא על ידי המודל.
  - `app/api/chat/route.ts`: נקודת הקצה של הצ'אט. המפתחות נשארים בצד השרת.
  - `app/page.tsx`: ממשק צ'אט בעברית (RTL) עם היסטוריה, שאלות המשך, תג התאמה והצגת הקטעים שנמצאו.

## הפעלה
1. ב-Supabase: פרויקט חדש, SQL Editor, מדביקים את `supabase/setup.sql` ומריצים.
2. מהגדרות הפרויקט (API) מעתיקים את ה-URL ואת המפתח הסודי (service_role / secret).
```
cd ingest
pip install -r requirements.txt
cp .env.example .env              # ממלאים מפתחות
python crawl.py                   # סריקה
python build_index.py             # העלאה ל-Supabase

cd ../web
npm install
cp .env.example .env.local        # GEMINI_API_KEY, SUPABASE_URL, SUPABASE_SERVICE_KEY
npm run dev                       # http://localhost:3000
```

## פריסה ל-Vercel
1. מעלים את התיקייה ל-GitHub (בלי קבצי `.env`).
2. ב-Vercel: Add New Project, בוחרים את הריפו, **Root Directory = `web`**.
3. תחת Environment Variables: `GEMINI_API_KEY`, `SUPABASE_URL`, `SUPABASE_SERVICE_KEY`.
4. Deploy.

## מגבלות
- מכסות חינמיות (Firecrawl 1,000 עמודים, Gemini לפי מגבלות הספק).
- פרויקט Supabase חינמי נרדם אחרי שבוע ללא פעילות.
- חיפוש מילות המפתח הוא בהגדרת `simple` (בלי הטיות בעברית), ולכן מועיל בעיקר לשמות מוצרים, מספרים וביטויים מדויקים.
- נסרקה רק חלק מהאתר; מה שלא נסרק יקבל "לא כתוב באתר".
- הבוט לא נותן ייעוץ אישי ולא ניגש למידע לקוח.

## רענון
להריץ שוב `crawl.py` ו-`build_index.py` (מוחק ומעלה מחדש את הטבלה). אין צורך בפריסה מחדש.
