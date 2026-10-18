"use server";

import { revalidatePath } from "next/cache";
import { redirect } from "next/navigation";

import { apiUpload, unwrap } from "@/lib/api";
import { errorState, type FormState } from "@/lib/form-state";
import { getTenant } from "@/lib/tenant";

export type LogoState = { error?: "logo_too_large" | "unsupported_image" | "generic"; saved?: boolean };

export async function updateDetails(_state: FormState, formData: FormData): Promise<FormState> {
  const { api, scope } = await getTenant();
  const value = (name: string) => String(formData.get(name) ?? "");
  // The weekly release is a weekday and a time together; "rolling" switches it off.
  const releaseWeekday = value("weekly_release_weekday");
  const weekly = releaseWeekday !== "" && value("weekly_release_time") !== "";
  try {
    unwrap(
      await api.PATCH("/tenants/current", {
        params: scope,
        body: {
          booking_horizon_days: Number(value("booking_horizon_days")) || 7,
          weekly_release_weekday: weekly ? Number(releaseWeekday) : null,
          weekly_release_time: weekly ? value("weekly_release_time") : null,
          name: value("name"),
          website_url: value("website_url").trim() || null,
          locale: value("locale") === "en" ? "en" : "he",
          time_zone: value("time_zone"),
          currency: value("currency"),
          cancellation_window_minutes: Number(value("cancellation_window_minutes")),
          booking_requires_plan: formData.get("booking_requires_plan") === "on",
          requires_health_declaration: formData.get("requires_health_declaration") === "on",
          client_id_number: ["optional", "required"].includes(value("client_id_number")) ? (value("client_id_number") as "optional" | "required") : "off",
          online_sales: formData.get("online_sales") === "on",
          require_mfa_for_staff: formData.get("require_mfa_for_staff") === "on",
          resource_payment: value("resource_payment") === "venue" ? "venue" : "app",
        },
      }),
    );
  } catch (error) {
    return errorState(error);
  }
  revalidatePath("/", "layout");
  return { saved: true };
}

export async function updateBrandColor(_state: FormState, formData: FormData): Promise<FormState> {
  const { api, scope } = await getTenant();
  const color = formData.get("use_default") === "on" ? null : String(formData.get("primary_color"));
  try {
    unwrap(await api.PATCH("/tenants/current", { params: scope, body: { primary_color: color } }));
  } catch (error) {
    return errorState(error);
  }
  revalidatePath("/", "layout");
  return { saved: true };
}

export async function uploadLogo(_state: LogoState, formData: FormData): Promise<LogoState> {
  const file = formData.get("logo");
  if (!(file instanceof File) || file.size === 0) return { error: "unsupported_image" };
  const { tenant } = await getTenant();
  const response = await apiUpload("/tenants/current/logo", file, tenant.id);
  if (response.status === 413) return { error: "logo_too_large" };
  if (response.status === 415) return { error: "unsupported_image" };
  if (!response.ok) return { error: "generic" };
  revalidatePath("/", "layout");
  return { saved: true };
}

export async function removeLogo(): Promise<void> {
  const { api, scope } = await getTenant();
  await api.DELETE("/tenants/current/logo", { params: scope });
  revalidatePath("/", "layout");
}

export type IdentityState = { error?: "invalid_business_number" | "generic"; saved?: boolean };

/** The business's legal entity and registration number (ח.פ., עוסק מורשה...). */
export async function updateIdentity(_state: IdentityState, formData: FormData): Promise<IdentityState> {
  const { api, scope } = await getTenant();
  const type = String(formData.get("legal_entity_type") ?? "");
  const response = await api.PATCH("/tenants/current", {
    params: scope,
    body: {
      legal_entity_type: (type || null) as "company" | null,
      business_number: String(formData.get("business_number") ?? ""),
    },
  });
  if (response.error) {
    const detail = (response.error as { detail?: unknown }).detail;
    return { error: detail === "invalid_business_number" ? "invalid_business_number" : "generic" };
  }
  revalidatePath("/settings");
  return { saved: true };
}

export async function uploadCover(_state: LogoState, formData: FormData): Promise<LogoState> {
  const file = formData.get("cover");
  if (!(file instanceof File) || file.size === 0) return { error: "unsupported_image" };
  const { tenant } = await getTenant();
  const response = await apiUpload("/tenants/current/cover", file, tenant.id);
  if (response.status === 413) return { error: "logo_too_large" };
  if (response.status === 415) return { error: "unsupported_image" };
  if (!response.ok) return { error: "generic" };
  revalidatePath("/", "layout");
  return { saved: true };
}

export async function removeCover(): Promise<void> {
  const { api, scope } = await getTenant();
  await api.DELETE("/tenants/current/cover", { params: scope });
  revalidatePath("/", "layout");
}

/** Address, employer file and the optional business licence (the legal-readiness card). */
export async function updateLegalDetails(_state: FormState, formData: FormData): Promise<FormState> {
  const { api, scope } = await getTenant();
  const value = (name: string) => String(formData.get(name) ?? "").trim();
  try {
    unwrap(
      await api.PATCH("/tenants/current", {
        params: scope,
        body: {
          address_line: value("address_line"),
          address_city: value("address_city"),
          employer_file_number: value("employer_file_number"),
          business_license_number: value("business_license_number"),
          business_license_expires_on: value("business_license_expires_on") || null,
        },
      }),
    );
  } catch (error) {
    return errorState(error);
  }
  revalidatePath("/settings");
  revalidatePath("/dashboard");
  return { saved: true };
}

export type BrandingState = { error?: NonNullable<FormState["error"]> | "logo_too_large" | "cover_too_large" | "unsupported_image"; saved?: boolean };

/** Everything on the branding page in one save: name, color, logo and cover (R13). */
export async function saveBranding(_state: BrandingState, formData: FormData): Promise<BrandingState> {
  const { api, scope, tenant } = await getTenant();
  const name = String(formData.get("name") ?? "").trim();
  const color = formData.get("use_default") === "on" ? null : String(formData.get("primary_color") ?? "");
  try {
    unwrap(await api.PATCH("/tenants/current", { params: scope, body: { ...(name ? { name } : {}), primary_color: color || null } }));
  } catch (error) {
    return errorState(error);
  }

  const upload = async (path: "/tenants/current/logo" | "/tenants/current/cover", file: FormDataEntryValue | null, tooLarge: BrandingState["error"]) => {
    if (!(file instanceof File) || file.size === 0) return null;
    const response = await apiUpload(path, file, tenant.id);
    if (response.status === 413) return tooLarge;
    if (response.status === 415) return "unsupported_image" as const;
    return response.ok ? null : ("generic" as const);
  };
  const logoError = await upload("/tenants/current/logo", formData.get("logo"), "logo_too_large");
  if (logoError) return { error: logoError };
  const coverError = await upload("/tenants/current/cover", formData.get("cover"), "cover_too_large");
  if (coverError) return { error: coverError };

  const hasFile = (field: string) => {
    const file = formData.get(field);
    return file instanceof File && file.size > 0;
  };
  if (formData.get("remove_logo") === "on" && !hasFile("logo")) await api.DELETE("/tenants/current/logo", { params: scope });
  if (formData.get("remove_cover") === "on" && !hasFile("cover")) await api.DELETE("/tenants/current/cover", { params: scope });

  revalidatePath("/", "layout");
  return { saved: true };
}

/** "I grew": ends solo mode, so the team, shifts, payroll and branch areas show up. */
export async function leaveSoloMode(): Promise<void> {
  const { api, scope } = await getTenant();
  unwrap(await api.PATCH("/tenants/current", { params: scope, body: { business_size: "small" } }));
  revalidatePath("/", "layout");
  redirect("/dashboard");
}
