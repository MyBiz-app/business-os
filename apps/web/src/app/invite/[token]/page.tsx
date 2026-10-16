import { MailPlus } from "lucide-react";
import { getTranslations } from "next-intl/server";
import Link from "next/link";

import { signOutToLogin } from "@/app/(auth)/actions";
import { AuthHeading, AuthShell } from "@/components/auth/auth-shell";
import { ScopedMessages } from "@/components/scoped-messages";
import { getApi } from "@/lib/api";
import { createClient } from "@/lib/supabase/server";

import { acceptInvitation } from "./actions";
import { isolate } from "@/lib/bidi";

const BUTTON = "btn-primary px-4 py-2.5 text-center";

export default async function InvitePage({ params }: PageProps<"/invite/[token]">) {
  const { token } = await params;
  const t = await getTranslations();
  const supabase = await createClient();
  const { data } = await supabase.auth.getClaims();
  const email = typeof data?.claims?.email === "string" ? data.claims.email : null;
  const next = encodeURIComponent(`/invite/${token}`);

  let content: React.ReactNode;
  if (!data?.claims) {
    content = (
      <>
        <p>{t("invite.signedOutBody")}</p>
        <div className="flex flex-col gap-3">
          <Link href={`/login?next=${next}`} className={BUTTON}>
            {t("invite.login")}
          </Link>
          <Link href={`/signup?next=${next}`} className="btn-secondary px-4 py-2.5">
            {t("invite.signup")}
          </Link>
        </div>
      </>
    );
  } else {
    const { data: invite } = await (await getApi()).GET("/invitations/{token}", {
      params: { path: { token } },
    });
    if (!invite) {
      content = <p>{t("invite.notFound")}</p>;
    } else if (invite.status !== "pending") {
      content = <p>{t(invite.status === "expired" ? "invite.expired" : "invite.accepted")}</p>;
    } else if (invite.email.toLowerCase() !== email?.toLowerCase()) {
      content = (
        <>
          <p>{t("invite.wrongEmail", { invited: isolate(invite.email), current: isolate(email ?? "") })}</p>
          <form action={signOutToLogin}>
            <button type="submit" className="btn-secondary w-full px-4 py-2.5">
              {t("auth.signOut")}
            </button>
          </form>
        </>
      );
    } else {
      content = (
        <>
          <p>{t("invite.body", { business: isolate(invite.tenant_name), role: t(`roles.${invite.role}`) })}</p>
          <form action={acceptInvitation.bind(null, token)}>
            <button type="submit" className={`${BUTTON} w-full`}>
              {t("invite.accept", { business: isolate(invite.tenant_name) })}
            </button>
          </form>
        </>
      );
    }
  }

  return (
    <ScopedMessages scopes={["auth"]}>
      <AuthShell>
        <AuthHeading title={t("invite.title")} icon={<MailPlus className="size-6" />} />
        {content}
      </AuthShell>
    </ScopedMessages>
  );
}
