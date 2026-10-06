import { AppRoot } from "@business-os/app-kit/components/app-root";
import { StaffProvider } from "@/providers/staff-provider";

export default function RootLayout() {
  return <AppRoot Provider={StaffProvider} />;
}
