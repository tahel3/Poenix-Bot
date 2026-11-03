import { NextRequest, NextResponse } from "next/server";
import { answer, NOT_FOUND } from "@/lib/rag";

export const maxDuration = 30;

export async function POST(req: NextRequest) {
  try {
    const { question, history } = await req.json();
    if (typeof question !== "string" || !question.trim() || question.length > 500) {
      return NextResponse.json({ error: "שאלה לא תקינה" }, { status: 400 });
    }
    const result = await answer(question.trim(), Array.isArray(history) ? history : []);
    return NextResponse.json(result);
  } catch (e: unknown) {
    console.error(e);
    const status = (e as { status?: number })?.status;
    if (status === 429) {
      return NextResponse.json(
        { answer: "הבוט הגיע למכסת הבקשות היומית. אנא נסה שוב מחר.", sources: [], score: 0, found: false, chunks: [] },
        { status: 503 }
      );
    }
    return NextResponse.json(
      { answer: "אירעה תקלה זמנית, נסי שוב בעוד רגע.", sources: [], score: 0, found: false, chunks: [], error: String(e) },
      { status: 500 }
    );
  }
}
