import type { Metadata } from "next";
import { Inter } from "next/font/google";

import "./globals.css";
import Providers from "./providers";
import { Toaster } from "@/components/ui/toaster";
import { cn } from "@/lib/utils";
import { TopNav } from "@/components/features/TopNav";

const inter = Inter({ subsets: ["latin"], variable: "--font-sans" });

export const metadata: Metadata = {
  title: "IntentKit Agent Platform",
  description: "Manage your autonomous agents",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body
        className={cn(
          "min-h-screen bg-background font-sans antialiased",
          inter.variable,
        )}
      >
        <Providers>
          <div className="relative flex min-h-screen flex-col">
            <header className="sticky top-0 z-50 w-full border-b border-border/40 bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
              <div className="container flex h-14 max-w-screen-2xl items-center">
                <TopNav />
              </div>
            </header>
            <main className="flex-1">{children}</main>
          </div>
        </Providers>
        <Toaster />
      </body>
    </html>
  );
}
