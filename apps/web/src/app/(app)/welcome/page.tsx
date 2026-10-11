import { Building2, FlaskConical, Sparkles } from "lucide-react";
import { getTranslations } from "next-intl/server";
import Link from "next/link";
import { redirect } from "next/navigation";

import { resumePath } from "@/lib/resume";
import { getActiveMembership } from "@/lib/tenant";

import { SampleForm } from "./sample-form";

/** Where a new account lands (decision T79): create the business now, or first explore a
 * sample business filled with fictitious data. People who already have a business go on,
 * and people who planned one in the sign-up journey return to its payment step. */
export default async function WelcomePage({ searchParams }: PageProps<"/welcome">) {
  const { membership } = await getActiveMembership();
  if (membership) redirect("/dashboard");
  // Signed up from the journey or an invitation, then signed in some other way (e.g. the
  // confirmation link opened in another browser): carry on from there, not from scratch.
  if (!(await searchParams).fresh) {
    const resume = await resumePath();
    if (resume) redirect(resume);
  }
  const t = await getTranslations("welcome");

  return (
    <main className="enter mx-auto flex w-full max-w-4xl flex-1 flex-col gap-8 px-4 py-12 sm:px-6">
      <div className="flex flex-col items-center gap-3 text-center">
        <span aria-hidden="true" className="flex size-14 items-center justify-center rounded-2xl bg-gradient-to-br from-brand-from to-brand-to text-white shadow-lg">
          <Sparkles className="size-7" />
        </span>
        <h1 className="text-3xl font-extrabold tracking-tight sm:text-4xl">{t("title")}</h1>
        <p className="max-w-xl text-lg text-muted">{t("subtitle")}</p>
      </div>
      <div className="grid gap-5 md:grid-cols-2">
        <section aria-labelledby="create-heading" className="card-accent flex flex-col gap-4 p-6">
          <span aria-hidden="true" className="icon-tile size-12">
            <Building2 className="size-6" />
          </span>
          <h2 id="create-heading" className="text-xl font-bold">
            {t("create.title")}
          </h2>
          <p className="flex-1 text-muted">{t("create.text")}</p>
          <Link href="/onboarding" className="btn-primary px-5 py-3">
            {t("create.button")}
          </Link>
        </section>
        <section aria-labelledby="sample-heading" className="card flex flex-col gap-4 p-6">
          <span aria-hidden="true" className="icon-tile size-12">
            <FlaskConical className="size-6" />
          </span>
          <h2 id="sample-heading" className="text-xl font-bold">
            {t("sample.title")}
          </h2>
          <p className="text-muted">{t("sample.text")}</p>
          <SampleForm />
        </section>
      </div>
    </main>
  );
}
