import type React from "react";
import type { Metadata } from "next";
import { Manrope } from "next/font/google";
import Script from "next/script";
import { MuiProvider } from "@/components/mui-provider";
import "./globals.css";

const manrope = Manrope({
  subsets: ["latin"],
  variable: "--font-manrope",
});

export const metadata: Metadata = {
  title: "ShiftFlow 餐饮排班助手",
  description: "面向奶茶、咖啡和快餐门店的对话式排班工作台",
  icons: {
    icon: "/openai_logo.svg",
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className={manrope.variable}>
      <body id="__next" className={manrope.className}>
        <Script
          src="https://cdn.platform.openai.com/deployments/chatkit/chatkit.js"
          strategy="beforeInteractive"
        />
        <MuiProvider>{children}</MuiProvider>
      </body>
    </html>
  );
}
