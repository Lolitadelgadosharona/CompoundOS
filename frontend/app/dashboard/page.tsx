import OwnerDashboard from "../../components/owner/dashboard";
import {redirect} from "next/navigation";
export default function DashboardPage(){if(process.env.COMPOUNDOS_PREVIEW_MODE !== "true")redirect("/investment");return <OwnerDashboard/>;}
