import type { Metadata } from "next";
import { Geist } from "next/font/google";
import "./globals.css";
import { ThemeProvider } from "@/components/theme-provider";
import { QueryProvider } from "@/components/query-provider";
import { Sidebar } from "@/components/sidebar";
import { ErrorBoundary } from "@/components/error-boundary";
import { I18nProvider } from "@/lib/i18n";
import { AppHeader } from "@/components/app-header";

const geist = Geist({ subsets: ["latin"], variable: "--font-geist-sans" });

export const metadata: Metadata = {
  title: "Finanse — Dashboard",
  description: "Self-hosted personal finance dashboard",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html
      lang="pl"
      suppressHydrationWarning
      className={`${geist.variable} h-full antialiased`}
    >
      <body className="min-h-full">
        <ThemeProvider attribute="class" defaultTheme="system" enableSystem>
          <I18nProvider>
            <QueryProvider>
              <div className="flex h-screen">
                <Sidebar />
                <div className="flex flex-1 flex-col overflow-hidden">
                  <AppHeader />
                  <main className="flex-1 overflow-y-auto p-6">
                    <ErrorBoundary>{children}</ErrorBoundary>
                  </main>
                </div>
              </div>
            </QueryProvider>
          </I18nProvider>
        </ThemeProvider>
      </body>
    </html>
  );
}
