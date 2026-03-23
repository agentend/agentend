import type { Metadata } from "next";
import "./globals.css";
import { Sidebar } from "@/components/sidebar";
import { StatusBar } from "@/components/status-bar";
import { SessionProvider } from "@/providers/session-provider";

export const metadata: Metadata = {
  title: "Agentend Console",
  description: "The Django for AI agent backends",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className="antialiased">
        <SessionProvider>
          <div className="flex h-screen">
            <Sidebar />
            <main className="flex-1 flex flex-col">
              <div className="flex-1 overflow-auto">{children}</div>
              <StatusBar />
            </main>
          </div>
        </SessionProvider>
      </body>
    </html>
  );
}
