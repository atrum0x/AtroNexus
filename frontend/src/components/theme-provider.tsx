"use client";

import { ThemeProvider as NextThemesProvider } from "next-themes";

/**
 * Light, dark or the device's setting (default). Puts the `dark` class on
 * <html>, which globals.css uses for the dark colours, and remembers the
 * choice in this browser.
 */
export function ThemeProvider({ children }: { children: React.ReactNode }) {
  return (
    <NextThemesProvider attribute="class" defaultTheme="system" enableSystem disableTransitionOnChange>
      {children}
    </NextThemesProvider>
  );
}
