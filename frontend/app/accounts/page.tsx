import View from "../../components/owner/accounts";
import { redirect } from "next/navigation";
export default function Page() {
  if (process.env.COMPOUNDOS_PREVIEW_MODE !== "true") redirect("/");
  return <View />;
}
