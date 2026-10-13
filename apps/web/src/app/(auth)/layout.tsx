import { AuthShell } from "@/components/auth/auth-shell";
import { ScopedMessages } from "@/components/scoped-messages";

/** Sign-in screens (login, signup, password reset, check email). */
export default function AuthLayout({ children }: LayoutProps<"/">) {
  return (
    <ScopedMessages scopes={["auth"]}>
      <AuthShell>{children}</AuthShell>
    </ScopedMessages>
  );
}
