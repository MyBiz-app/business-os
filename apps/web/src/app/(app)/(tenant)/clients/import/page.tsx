import { getTranslations } from "next-intl/server";
import Link from "next/link";

import { getTenantFor } from "@/lib/tenant";

import { ImportForm } from "./import-form";

export default async function ImportClientsPage() {
  const t = await getTranslations("clientImport");
  const tClients = await getTranslations("clients");
  await getTenantFor("clients.write");

  return (
    <main className="mx-auto flex w-full max-w-3xl flex-1 flex-col gap-6 px-6 py-10">
      <Link href="/clients" className="text-sm text-primary underline-offset-4 hover:underline">
        {tClients("back")}
      </Link>
      <div className="flex flex-col gap-1">
        <h1 className="text-3xl font-bold">{t("title")}</h1>
        <p className="text-muted">{t("intro")}</p>
      </div>
      <ImportForm />
    </main>
  );
}
