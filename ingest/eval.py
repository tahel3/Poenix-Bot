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
    res = ask(q["q"])
    got = "answer" if res["found"] else "refuse"
    good = got == q["expect"]
    ok += good
    rows.append({"q": q["q"], "expect": q["expect"], "got": got,
                 "score": round(res["score"], 2), "ok": good, "answer": res["answer"]})
    print(("✅" if good else "❌"), q["q"], f"(ציפינו: {q['expect']}, קיבלנו: {got}, ציון {res['score']:.2f})")
    time.sleep(1.5)

print(f"\nדיוק כולל: {ok}/{len(questions)} = {ok / len(questions):.0%}")
inventions = [r for r in rows if r["expect"] == "refuse" and r["got"] == "answer"]
print(f"המצאות (ענה במקום לסרב): {len(inventions)}")
print("שאלות שנכשלו בודקים ידנית מול האתר, ומכווננים MIN_SIMILARITY או את ההנחיה.")

with open("eval_results.json", "w", encoding="utf-8") as f:
    json.dump(rows, f, ensure_ascii=False, indent=2)
