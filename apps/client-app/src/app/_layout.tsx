import { AppRoot } from "@business-os/app-kit/components/app-root";
import { AppProviders } from "@/providers/app-providers";

export default function RootLayout() {
  return <AppRoot Provider={AppProviders} />;
}
