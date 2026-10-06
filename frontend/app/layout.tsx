import type { Metadata } from "next";
import type { ReactNode } from "react";

import "./globals.css";

export const metadata: Metadata = {
  title: "CompoundOS",
  description: "Local household discipline workspace for CompoundOS",
};

export default function RootLayout({ children }: Readonly<{ children: ReactNode }>) {
  return (
    <html lang="en">
      <body>
        {process.env.COMPOUNDOS_PREVIEW_MODE === "true" && <aside role="note" style={{position:"sticky",top:0,zIndex:1000,padding:"16px",background:"#fff0b3",color:"#422c00",borderBottom:"3px solid #b85c00",fontWeight:700}}>
          OWNER PREVIEW · DEMO DATA · SIMULATED COMMITTEE<br />NO REAL INVESTMENT RECOMMENDATION · NO TRADES WILL BE EXECUTED
        </aside>}
        {children}</body>
    </html>
  );
}
