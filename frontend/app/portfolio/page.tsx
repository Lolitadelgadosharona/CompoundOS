import { redirect } from "next/navigation";
import { PortfolioClient } from "./portfolio-client";

export default function PortfolioPage() {
  if (process.env.COMPOUNDOS_PREVIEW_MODE === "true") redirect("/investment#portfolio");
  return <PortfolioClient />;
}
