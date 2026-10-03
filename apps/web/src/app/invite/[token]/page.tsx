import { getTranslations } from "next-intl/server";
import Link from "next/link";

import { signOut } from "@/app/(auth)/actions";
import { AppHeader } from "@/components/app-header";
import { getApi } from "@/lib/api";
import { createClient } from "@/lib/supabase/server";

import { acceptInvitation } from "./actions";

const BUTTON = "rounded-lg bg-primary px-4 py-2.5 text-center font-semibold text-on-primary";

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
          <Link href={`/signup?next=${next}`} className="rounded-lg border border-border px-4 py-2.5 text-center font-semibold">
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
          <p>{t("invite.wrongEmail", { invited: invite.email, current: email ?? "" })}</p>
          <form action={signOut}>
            <button type="submit" className="text-sm text-primary underline-offset-4 hover:underline">
              {t("auth.signOut")}
            </button>
          </form>
        </>
      );
    } else {
      content = (
        <>
          <p>{t("invite.body", { business: invite.tenant_name, role: t(`roles.${invite.role}`) })}</p>
          <form action={acceptInvitation.bind(null, token)}>
            <button type="submit" className={`${BUTTON} w-full`}>
              {t("invite.accept", { business: invite.tenant_name })}
            </button>
          </form>
        </>
      );
    }
  }

  return (
    <div className="flex flex-1 flex-col">
      <AppHeader />
      <main className="flex flex-1 items-start justify-center px-4 py-16">
        <div className="flex w-full max-w-sm flex-col gap-6 rounded-2xl border border-border bg-surface p-6 sm:p-8">
          <h1 className="text-2xl font-bold">{t("invite.title")}</h1>
          {content}
        </div>
      </main>
    </div>
  );
}
