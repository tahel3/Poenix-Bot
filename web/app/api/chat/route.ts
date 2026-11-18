import { NextRequest, NextResponse } from "next/server";
import { answer } from "@/lib/rag";

export const maxDuration = 90;

export async function POST(req: NextRequest) {
  let lang: "he" | "en" = "he";
  try {
    const { question, history, lang: rawLang } = await req.json();
    lang = rawLang === "en" ? "en" : "he";
    if (typeof question !== "string" || !question.trim() || question.length > 500) {
      return NextResponse.json({ error: lang === "en" ? "Invalid question" : "שאלה לא תקינה" }, { status: 400 });
    }
    const result = await answer(question.trim(), Array.isArray(history) ? history : [], lang);
    return NextResponse.json(result);
  } catch (e: unknown) {
    console.error(e);
    const status = (e as { status?: number })?.status;
    if (status === 429) {
      return NextResponse.json(
        { answer: lang === "en" ? "The bot has reached its daily request limit. Please try again tomorrow." : "הבוט הגיע למכסת הבקשות היומית. אנא נסה שוב מחר.", sources: [], score: 0, found: false, chunks: [] },
        { status: 503 }
      );
    }
    return NextResponse.json(
      { answer: lang === "en" ? "Something went wrong. Please try again in a moment." : "אירעה תקלה זמנית, נסי שוב בעוד רגע.", sources: [], score: 0, found: false, chunks: [], error: String(e) },
      { status: 500 }
    );
  }
}
