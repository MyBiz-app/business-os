import { redirect } from "next/navigation";

import { unwrap } from "@/lib/api";
import { getTenant } from "@/lib/tenant";

import { normalize } from "./draft";
import { WebsiteWizard } from "./wizard";

/** The wizard with the saved draft; shared by the window and the full page. */
export async function WizardBody() {
  const { api, scope, tenant } = await getTenant();
  const state = unwrap(await api.GET("/website/order", { params: scope }));
  // Once MyBiz builds, the brief no longer changes.
  if (state.order && state.order.stage !== "briefing" && state.order.stage !== "received") redirect("/website");
  const brief = normalize(state.order?.brief);
  // File names for the images already uploaded.
  const ids = new Set([...brief.images.map((image) => image.file_id), ...(brief.logo_file_id ? [brief.logo_file_id] : [])]);
  const fileNames: Record<string, string> = {};
  if (ids.size > 0) {
    const files = unwrap(await api.GET("/files", { params: { ...scope, query: { folder_id: state.files_folder_id } } }));
    for (const file of files) if (ids.has(file.id)) fileNames[file.id] = file.name;
  }
  return <WebsiteWizard initial={brief} folderId={state.files_folder_id} withSystem={state.with_system} brandColor={tenant.primary_color ?? ""} fileNames={fileNames} />;
}
