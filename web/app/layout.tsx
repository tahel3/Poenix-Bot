import "./globals.css";
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "הבוט של הפניקס",
  description: "עונה אך ורק מתוך המידע שבאתר הפניקס, עם מקור לכל תשובה",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="he" dir="rtl">
      <body>{children}</body>
    </html>
  );
}
