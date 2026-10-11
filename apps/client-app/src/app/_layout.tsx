import { AppRoot } from "@business-os/app-kit/components/app-root";
import { BusinessProvider } from "@/providers/business-provider";

export default function RootLayout() {
  return <AppRoot Provider={BusinessProvider} />;
}
