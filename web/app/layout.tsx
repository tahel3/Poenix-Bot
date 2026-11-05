import "./globals.css";
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "הבוט של הפניקס",
  description: "עונה אך ורק מתוך המידע שבאתר הפניקס, עם מקור לכל תשובה",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="he" dir="rtl">
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
        <link
          href="https://fonts.googleapis.com/css2?family=Rubik:wght@400;500;600;700&display=swap"
          rel="stylesheet"
        />
      </head>
      <body>{children}</body>
    </html>
  );
}
