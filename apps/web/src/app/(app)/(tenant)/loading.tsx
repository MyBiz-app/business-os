import { getTranslations } from "next-intl/server";

/** Shown instantly while a page of the business area loads: the shape of a typical page. */
export default async function Loading() {
  const t = await getTranslations("common");
  return (
    <main aria-busy="true" className="mx-auto flex w-full max-w-5xl flex-1 flex-col gap-6 px-6 py-10">
      <span role="status" className="sr-only">
        {t("loading")}
      </span>
      <div aria-hidden="true" className="flex flex-col gap-3">
        <div className="skeleton h-4 w-40" />
        <div className="skeleton h-9 w-72" />
      </div>
      <div aria-hidden="true" className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {Array.from({ length: 3 }, (_, i) => (
          <div key={i} className="card flex flex-col gap-3 p-5">
            <div className="skeleton h-4 w-24" />
            <div className="skeleton h-8 w-32" />
          </div>
        ))}
      </div>
      <div aria-hidden="true" className="card flex flex-col gap-3 p-6">
        {Array.from({ length: 5 }, (_, i) => (
          <div key={i} className="skeleton h-10 w-full" />
        ))}
      </div>
    </main>
  );
}
