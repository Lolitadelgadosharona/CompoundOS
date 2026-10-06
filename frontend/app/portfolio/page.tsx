import OwnerPortfolio from "../../components/owner/portfolio";
import { PortfolioClient } from "./portfolio-client";

export default function PortfolioPage() {
  if (process.env.COMPOUNDOS_PREVIEW_MODE === "true") return <OwnerPortfolio/>;
  return <PortfolioClient />;
}
