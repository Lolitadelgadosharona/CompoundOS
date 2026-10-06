import { redirect } from "next/navigation";
import CommitteeClient from "./committee-client";

export default function CommitteePage() {
  if (process.env.COMPOUNDOS_PREVIEW_MODE === "true") redirect("/investment-plan#discussion");
  return <CommitteeClient />;
}
