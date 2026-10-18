import { Archive, Download, FileText, FolderOpen, FolderPlus, Lock, Trash2 } from "lucide-react";
import { getLocale, getTranslations } from "next-intl/server";
import Link from "next/link";

import { EmptyState } from "@/components/empty-state";
import { Container } from "@/components/layout/container";
import { PageHeader } from "@/components/layout/page-header";
import { Pill } from "@/components/pill";
import { unwrap } from "@/lib/api";
import { getTenantFor } from "@/lib/tenant";

import { deleteFile, deleteFolder } from "./actions";
import { ArchiveButton } from "./archive-button";
import { NewFolderForm, UploadForm } from "./forms";
import { CollapsibleSection } from "@/components/ui/collapsible-section";
import { ContentSwap } from "@/components/ui/content-swap";
import { LinkSegmented } from "@/components/ui/link-segmented";

const SYSTEM_KEYS = ["payroll", "employees", "business_docs", "imports", "website", "general"] as const;

/** The business's files (round 6, F1): system folders plus its own, each opened by its own permission. */
export default async function FilesPage({ searchParams }: PageProps<"/files">) {
  const t = await getTranslations("files");
  const tc = await getTranslations("common");
  const locale = await getLocale();
  const { tenant, api, scope } = await getTenantFor("files.read");
  const query = await searchParams;
  const folders = unwrap(await api.GET("/files/folders", { params: scope }));
  const requested = typeof query.folder === "string" ? query.folder : undefined;
  const open = folders.find((f) => f.id === requested) ?? folders.find((f) => f.system_key === "general") ?? folders[0];
  const showArchived = query.archived === "1";
  const files = open
    ? unwrap(await api.GET("/files", { params: { ...scope, query: { folder_id: open.id, archived: showArchived } } }))
    : [];
  const canManage = tenant.permissions.includes("files.manage");

  const folderName = (folder: (typeof folders)[number]) =>
    folder.system_key && (SYSTEM_KEYS as readonly string[]).includes(folder.system_key)
      ? t(`system.${folder.system_key as (typeof SYSTEM_KEYS)[number]}`)
      : folder.name;
  const date = new Intl.DateTimeFormat(locale, { dateStyle: "medium", timeZone: tenant.time_zone });
  const size = new Intl.NumberFormat(locale, { style: "unit", unit: "kilobyte", maximumFractionDigits: 0 });
  // Subfolders sit under their parent, one level of indent each.
  const depthOf = (id: string | null): number => {
    const parent = folders.find((f) => f.id === id);
    return parent ? 1 + depthOf(parent.parent_id) : 0;
  };
  const children = folders.filter((f) => f.parent_id === open?.id);
  // The top row slides between the top-level folders; folders inside the open one show as chips below.
  const roots = folders.filter((f) => f.parent_id === null);
  const rootOf = (folder: (typeof folders)[number] | undefined): (typeof folders)[number] | undefined => {
    let current = folder;
    while (current?.parent_id) current = folders.find((f) => f.id === current?.parent_id);
    return current;
  };
  const rootOfOpen = rootOf(open);
  const descendantsOf = (id: string): typeof folders => folders.filter((f) => f.parent_id === id).flatMap((f) => [f, ...descendantsOf(f.id)]);
  const inside = rootOfOpen ? descendantsOf(rootOfOpen.id) : [];

  return (
    <Container as="main" size="full" className="enter flex flex-1 flex-col gap-6 py-8 sm:py-10">
      <PageHeader
        title={
          <span className="flex items-center gap-3">
            <FolderOpen aria-hidden="true" className="size-8 shrink-0 text-primary-ink" />
            {t("title")}
          </span>
        }
        description={t("subtitle")}
      />
      <div className="flex flex-col gap-6">
        <div className="flex flex-col gap-3">
          <div className="overflow-x-auto pb-1">
            <LinkSegmented
              label={t("rootFolders")}
              loadingLabel={tc("loading")}
              active={rootOfOpen?.id ?? ""}
              options={roots.map((folder) => ({ key: folder.id, label: `${folderName(folder)} · ${folder.file_count}`, href: `/files?folder=${folder.id}` }))}
            />
          </div>
          {inside.length > 0 && (
            <LinkSegmented
              variant="chips"
              label={t("subfolders")}
              loadingLabel={tc("loading")}
              active={open?.id ?? ""}
              options={[rootOfOpen, ...inside].filter((f): f is (typeof folders)[number] => !!f).map((folder) => ({
                key: folder.id,
                label: `${"› ".repeat(Math.max(0, depthOf(folder.parent_id) - (rootOfOpen ? depthOf(rootOfOpen.parent_id) + 1 : 0)))}${folderName(folder)} · ${folder.file_count}`,
                href: `/files?folder=${folder.id}`,
              }))}
            />
          )}
        </div>

        <ContentSwap swapKey={`${open?.id ?? "none"}-${showArchived ? "a" : "f"}`}>
        {open ? (
          <section aria-labelledby="folder-heading" className="card flex flex-col gap-5 p-6">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div className="flex min-w-0 flex-col gap-1">
                <h2 id="folder-heading" className="truncate text-lg font-semibold" dir="auto">{folderName(open)}</h2>
                <p className="flex flex-wrap items-center gap-2 text-sm text-muted">
                  {t("count", { count: open.file_count })}
                  {open.sensitive && <Pill tone="muted"><Lock aria-hidden="true" className="size-3" /> {t("sealed")}</Pill>}
                  {open.retain && <Pill tone="muted">{t("kept")}</Pill>}
                </p>
              </div>
              <div className="flex flex-wrap items-center gap-2">
                <Link scroll={false} href={`/files?folder=${open.id}${showArchived ? "" : "&archived=1"}`} className="btn-secondary px-3 py-1.5 text-sm">
                  <Archive aria-hidden="true" className="size-4" /> {showArchived ? t("hideArchived") : t("showArchived")}
                </Link>
                {open.file_count > 0 && (
                  <a href={`/files/folders/${open.id}/zip`} download className="btn-secondary px-3 py-1.5 text-sm">
                    <Download aria-hidden="true" className="size-4" /> {t("zip")}
                  </a>
                )}
              </div>
            </div>

            {open.system_key === "imports" && <p className="text-sm text-muted">{t("importsHint")}</p>}
            {open.system_key === "payroll" && <p className="text-sm text-muted">{t("payrollHint")}</p>}

            {files.length === 0 ? (
              <EmptyState variant="list">{showArchived ? t("noneArchived") : t("none")}</EmptyState>
            ) : (
              <ul className="flex flex-col divide-y divide-border">
                {files.map((file) => (
                  <li key={file.id} className="flex flex-wrap items-center justify-between gap-2 py-2.5">
                    <div className="flex min-w-0 flex-col gap-0.5">
                      <a href={`/files/${file.id}/file`} className="flex items-center gap-2 truncate font-medium text-primary-ink underline-offset-4 hover:underline" dir="auto">
                        <FileText aria-hidden="true" className="size-4 shrink-0" />
                        {file.name}
                      </a>
                      <span className="text-xs text-muted">
                        {date.format(new Date(file.created_at))} · {size.format(Math.max(1, Math.round(file.size / 1024)))}
                        {file.owner_name && ` · ${file.owner_name}`}
                        {file.expires_at && ` · ${t("expires", { date: date.format(new Date(file.expires_at)) })}`}
                      </span>
                    </div>
                    {open.can_upload && (
                      <div className="flex items-center gap-1">
                        <ArchiveButton
                          fileId={file.id}
                          name={file.name}
                          archived={!!file.archived_at}
                          labels={{
                            archive: t("archive"),
                            restore: t("restore"),
                            archived: t("archivedToast", { name: file.name }),
                            restored: t("restoredToast", { name: file.name }),
                            undo: tc("undo"),
                          }}
                        />
                        {!open.retain && (
                          <form action={deleteFile.bind(null, file.id)}>
                            <button type="submit" aria-label={t("delete", { name: file.name })} className="btn-plain rounded-lg p-1 text-muted hover:bg-danger/10 hover:text-danger">
                              <Trash2 aria-hidden="true" className="size-4" />
                            </button>
                          </form>
                        )}
                      </div>
                    )}
                  </li>
                ))}
              </ul>
            )}

            {open.can_upload && (
              <CollapsibleSection title={t("add")}>
                <UploadForm folderId={open.id} />
              </CollapsibleSection>
            )}
            {canManage && open.can_upload && (
              <CollapsibleSection icon={<FolderPlus aria-hidden="true" className="size-4" />} title={t("newFolder")}>
                <NewFolderForm parentId={open.id} />
              </CollapsibleSection>
            )}
            {canManage && !open.system_key && open.file_count === 0 && children.length === 0 && (
              <form action={deleteFolder.bind(null, open.id, open.parent_id)}>
                <button type="submit" className="btn-secondary px-3 py-1.5 text-sm text-danger">
                  <Trash2 aria-hidden="true" className="size-4" /> {t("deleteFolder")}
                </button>
              </form>
            )}
          </section>
        ) : (
          <EmptyState variant="list">{t("noFolders")}</EmptyState>
        )}
        </ContentSwap>
      </div>
    </Container>
  );
}
