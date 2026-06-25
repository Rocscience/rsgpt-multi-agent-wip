import type { Metadata } from "next";
import { inter } from "@/lib/fonts";
import "./globals.css";
import { Providers } from "./providers";
import { ServiceStatusAlert } from '@/components/alerts/service-status-banner';
import { OfflineAlert } from '@/components/alerts/offline-alert';

export const metadata: Metadata = {
  title: "RSInsight",
  description: "Created by Rocscience",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body
        className={`${inter.className} antialiased`}
      >
        <Providers>
          <OfflineAlert />
          <ServiceStatusAlert />
          {children}
        </Providers>
      </body>
    </html>
  );
}
