import type { Metadata } from "next";
import type { ReactNode } from "react";

import "./globals.css";
import OwnerNavigation from "../components/owner/navigation";
import PreviewNotice from "../components/owner/preview-notice";

export const metadata: Metadata = {
  title: "CompoundOS",
  description: "Local household discipline workspace for CompoundOS",
};

export default function RootLayout({ children }: Readonly<{ children: ReactNode }>) {
  return (
    <html lang="en">
      <body>
        {process.env.COMPOUNDOS_PREVIEW_MODE === "true" && <PreviewNotice />}
        {process.env.COMPOUNDOS_PREVIEW_MODE === "true" && <OwnerNavigation />}
        {children}</body>
    </html>
  );
}
