"use server";

import type { components } from "@business-os/api-client";
import { redirect } from "next/navigation";

import { ApiError, getApi, type Tenant, unwrap } from "@/lib/api";
import { setActiveTenant } from "@/lib/tenant";

export type OnboardingState = { error?: "invalid" | "generic" };
type Questionnaire = components["schemas"]["QuestionnaireIn"];
type Selection = components["schemas"]["Selection"]["modules"];

export async function recommendModules(answers: Questionnaire): Promise<Selection> {
  const recommendation = unwrap(await (await getApi()).POST("/modules/recommend", { body: answers }));
  return recommendation.modules;
}

export async function createBusiness(
  _state: OnboardingState,
  formData: FormData,
): Promise<OnboardingState> {
  let modules: Selection | undefined;
  try {
    modules = JSON.parse(String(formData.get("modules") ?? "null")) ?? undefined;
  } catch {
    return { error: "invalid" };
  }
  const body = {
    name: String(formData.get("name") ?? ""),
    vertical: String(formData.get("vertical") ?? ""),
    locale: formData.get("locale") === "en" ? ("en" as const) : ("he" as const),
    time_zone: String(formData.get("time_zone") ?? ""),
    currency: String(formData.get("currency") ?? ""),
    modules,
  };

  let tenant: Tenant;
  try {
    tenant = unwrap(await (await getApi()).POST("/tenants", { body }));
  } catch (error) {
    return { error: error instanceof ApiError && error.status === 422 ? "invalid" : "generic" };
  }

  await setActiveTenant(tenant.id);
  redirect("/dashboard");
}
