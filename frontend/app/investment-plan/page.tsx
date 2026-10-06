import View from "../../components/owner/investment-plan";
import { redirect } from "next/navigation";
export default function Page() {
  if (process.env.COMPOUNDOS_PREVIEW_MODE !== "true") redirect("/");
  return <View />;
}
