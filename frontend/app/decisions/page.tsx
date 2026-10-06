import OwnerDecisions from "../../components/owner/decisions";
import { DecisionClient } from "./decision-client";

export default function DecisionsPage() {
  if (process.env.COMPOUNDOS_PREVIEW_MODE === "true") return <OwnerDecisions/>;
  return <DecisionClient />;
}
