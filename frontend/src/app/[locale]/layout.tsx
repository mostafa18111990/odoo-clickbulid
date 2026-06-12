import type { Metadata } from "next";
import { NextIntlClientProvider } from "next-intl";
import { getMessages } from "next-intl/server";
import { Cairo, Inter } from "next/font/google";
import "../globals.css";

const cairo = Cairo({ subsets: ["arabic", "latin"], variable: "--font-arabic" });
const inter  = Inter({ subsets: ["latin"], variable: "--font-latin" });

export const metadata: Metadata = {
  title: "ClickBuild — Odoo Cloud Platform",
  description: "منصة Odoo السحابية للشركات العربية",
};

export default async function LocaleLayout({
  children,
  params: { locale },
}: {
  children: React.ReactNode;
  params: { locale: string };
}) {
  const messages = await getMessages();
  const isRtl    = locale === "ar";

  return (
    <html lang={locale} dir={isRtl ? "rtl" : "ltr"}>
      <body className={`${cairo.variable} ${inter.variable} ${isRtl ? "font-arabic" : "font-latin"} antialiased`}>
        <NextIntlClientProvider messages={messages}>
          {children}
        </NextIntlClientProvider>
      </body>
    </html>
  );
}
