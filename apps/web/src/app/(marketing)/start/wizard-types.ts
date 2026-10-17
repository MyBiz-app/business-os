import type { Currency, SignupPlan } from "@/lib/signup-plan";

/** The plan being built: the signup plan, with the kind of business not chosen yet. */
export type Draft = Omit<SignupPlan, "vertical"> & { vertical: string | null };

export type { Currency };
