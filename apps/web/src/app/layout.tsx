import type { Metadata } from "next";
import { Geist } from "next/font/google";
import "./globals.css";
import { ThemeProvider } from "@/components/theme-provider";
import { AccentProvider } from "@/components/accent-provider";
import { QueryProvider } from "@/components/query-provider";
import { Sidebar } from "@/components/sidebar";
import { ErrorBoundary } from "@/components/error-boundary";
import { I18nProvider } from "@/lib/i18n";
import { AppHeader } from "@/components/app-header";
import { ConfirmProvider } from "@/components/confirm-dialog";
import { Toaster } from "@/components/ui/sonner";
import { TooltipProvider } from "@/components/ui/tooltip";

const geist = Geist({ subsets: ["latin"], variable: "--font-geist-sans" });

export const metadata: Metadata = {
  title: "Finanse — Pulpit",
  description: "Self-hosted personal finance dashboard",
};

// Set the saved accent before paint to avoid a flash of the default theme.
const accentScript = `(function(){try{var a=localStorage.getItem('finance-accent');document.documentElement.setAttribute('data-accent',(a==='teal'||a==='blue'||a==='violet')?a:'emerald');}catch(e){document.documentElement.setAttribute('data-accent','emerald');}})();`;

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html
      lang="pl"
      suppressHydrationWarning
      className={`${geist.variable} h-full antialiased`}
      data-accent="emerald"
    >
      <head>
        <script dangerouslySetInnerHTML={{ __html: accentScript }} />
      </head>
      <body className="min-h-full">
        <ThemeProvider attribute="class" defaultTheme="system" enableSystem>
          <AccentProvider>
            <I18nProvider>
              <QueryProvider>
                <TooltipProvider delayDuration={200}>
                  <ConfirmProvider>
                    <div className="flex h-screen">
                      <Sidebar />
                      <div className="flex min-w-0 flex-1 flex-col overflow-hidden">
                        <AppHeader />
                        <main className="min-w-0 flex-1 overflow-y-auto p-4 sm:p-6">
                          <ErrorBoundary>{children}</ErrorBoundary>
                        </main>
                      </div>
                    </div>
                    <Toaster />
                  </ConfirmProvider>
                </TooltipProvider>
              </QueryProvider>
            </I18nProvider>
          </AccentProvider>
        </ThemeProvider>
      </body>
    </html>
  );
}
