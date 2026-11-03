"""הערכה: שולח שאלות לבוט (דרך ה-API שלו) ומחשב כמה פעמים ענה / סירב נכון.

הרצה:
  python eval.py                         # מול השרת המקומי (npm run dev)
  python eval.py https://your-app.vercel.app   # מול הגרסה בענן

עורכים את questions.json: 20 שאלות עם "expect": "answer" ו-10 עם "expect": "refuse".
זה חצי מהציון בעולם האמיתי: לא להמציא.
"""
import json
import sys
import time
import urllib.request

BASE = (sys.argv[1] if len(sys.argv) > 1 else "http://localhost:3000").rstrip("/")

with open("questions.json", encoding="utf-8") as f:
    questions = json.load(f)


def ask(q):
    req = urllib.request.Request(
        BASE + "/api/chat",
        data=json.dumps({"question": q, "history": []}).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode("utf-8"))


rows, ok = [], 0
for q in questions:
    try:
        res = ask(q["q"])
    except Exception as e:
        print(f"⚠️  שגיאת רשת בשאלה «{q['q']}»: {e}")
        print("   וודא ש-npm run dev רץ ואז הרץ שוב את eval.py")
        break
    got = "answer" if res["found"] else "refuse"
    good = got == q["expect"]
    ok += good
    rows.append({"q": q["q"], "expect": q["expect"], "got": got,
                 "score": round(res["score"], 2), "ok": good, "answer": res["answer"]})
    print(("✅" if good else "❌"), q["q"], f"(ציפינו: {q['expect']}, קיבלנו: {got}, ציון {res['score']:.2f})")
    time.sleep(1.5)

total = len(rows)
if total:
    print(f"\nדיוק כולל: {ok}/{total} = {ok / total:.0%}")
    inventions = [r for r in rows if r["expect"] == "refuse" and r["got"] == "answer"]
    print(f"המצאות (ענה במקום לסרב): {len(inventions)}")
    if total < len(questions):
        print(f"⚠️  הריצה עצרה אחרי {total}/{len(questions)} שאלות (ראה שגיאה למעלה)")
    print("שאלות שנכשלו בודקים ידנית מול האתר, ומכווננים MIN_SIMILARITY או את ההנחיה.")

    with open("eval_results.json", "w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False, indent=2)
    print("תוצאות נשמרו ל-eval_results.json")
else:
    print("לא הושלמה אף שאלה — בדוק שה-server רץ.")
