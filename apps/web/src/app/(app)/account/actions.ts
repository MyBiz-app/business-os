"use server";

import { revalidatePath } from "next/cache";

import { getApi, unwrap } from "@/lib/api";
import { errorState, type FormState } from "@/lib/form-state";

export async function saveProfile(_state: FormState, formData: FormData): Promise<FormState> {
  try {
    unwrap(await (await getApi()).PATCH("/me", { body: { full_name: String(formData.get("full_name") ?? "") } }));
  } catch (error) {
    return errorState(error);
  }
  revalidatePath("/", "layout");
  return { saved: true };
}
