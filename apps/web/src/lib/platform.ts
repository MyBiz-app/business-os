import "server-only";

import type { components } from "@business-os/api-client";
import { notFound } from "next/navigation";
import { cache } from "react";

import { getApi } from "@/lib/api";

export type PlatformPermission = components["schemas"]["PlatformPermission"];
export type StaffLevel = components["schemas"]["StaffMe"]["level"];

export const PLATFORM_PERMISSIONS: PlatformPermission[] = [
  "businesses.read",
  "businesses.act",
  "billing.manage",
  "inbox.manage",
  "usage.read",
  "staff.manage",
];

/** The signed-in MyBiz team member (404 for everyone else) and what they may do. */
export const getPlatform = cache(async () => {
  const api = await getApi();
  const { data: staff } = await api.GET("/platform/me");
  if (!staff) notFound();
  const can = (permission: PlatformPermission) => staff.permissions.includes(permission);
  const isOwner = staff.level === "primary_owner" || staff.level === "owner";
  return { api, staff, can, isOwner };
});

/** For a console page that needs a permission. */
export async function getPlatformFor(permission: PlatformPermission) {
  const context = await getPlatform();
  if (!context.can(permission)) notFound();
  return context;
}
