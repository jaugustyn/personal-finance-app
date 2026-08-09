import type { Metadata } from "next";
import { cookies } from "next/headers";
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
import { DocumentTitle } from "@/components/document-title";
import { Toaster } from "@/components/ui/sonner";
import { TooltipProvider } from "@/components/ui/tooltip";
import { AppLockProvider } from "@/components/app-lock-provider";
import { SkipLink } from "@/components/skip-link";
import type { Locale } from "@/lib/i18n";
import { DICT } from "@/lib/i18n/locales";

const geist = Geist({ subsets: ["latin"], variable: "--font-geist-sans" });

export async function generateMetadata(): Promise<Metadata> {
  const locale = await localeFromCookie();
  return {
    title: DICT[locale]["metadata.title"],
    description: DICT[locale]["metadata.description"],
  };
}

// Set the saved accent before paint to avoid a flash of the default theme.
const accentScript = `(function(){try{var a=localStorage.getItem('finance-accent');document.documentElement.setAttribute('data-accent',(a==='teal'||a==='blue'||a==='violet')?a:'emerald');}catch(e){document.documentElement.setAttribute('data-accent','emerald');}})();`;

export default async function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  const initialLocale = await localeFromCookie();

  return (
    <html
      lang={initialLocale}
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
            <I18nProvider initialLocale={initialLocale}>
              <DocumentTitle />
              <QueryProvider>
                <TooltipProvider delayDuration={200}>
                  <ConfirmProvider>
                    <AppLockProvider>
                      <SkipLink />
                      <div className="flex h-screen">
                        <Sidebar />
                        <div className="flex min-w-0 flex-1 flex-col overflow-hidden">
                          <AppHeader />
                          <main id="main-content" tabIndex={-1} className="min-w-0 flex-1 overflow-y-auto [scrollbar-gutter:stable] p-4 sm:p-6">
                            <ErrorBoundary>{children}</ErrorBoundary>
                          </main>
                        </div>
                      </div>
                    </AppLockProvider>
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

async function localeFromCookie(): Promise<Locale> {
  const value = (await cookies()).get("finance-locale")?.value;
  return value === "en" ? "en" : "pl";
}
