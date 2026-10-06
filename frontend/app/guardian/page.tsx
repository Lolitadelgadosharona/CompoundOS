import { redirect } from "next/navigation";
import GuardianClient from "./guardian-client";

export default function GuardianPage() {
  if (process.env.COMPOUNDOS_PREVIEW_MODE === "true") redirect("/investment#owner-review");
  return <GuardianClient />;
}
