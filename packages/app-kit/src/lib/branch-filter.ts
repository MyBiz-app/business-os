/** Narrowing the client calendar to one branch, or to one kind of branch ("strength", "pilates"). */
export type BranchLike = { id: string; name: string; kind?: string | null };

export type BranchFilter = { branchId: string | null; kind: string | null };

export const ALL_BRANCHES: BranchFilter = { branchId: null, kind: null };

/** Up to this many branches are shown as chips; more go into a menu. */
export const MAX_BRANCH_CHIPS = 4;

/** The branch kinds the business uses, in the order of first appearance. */
export function branchKinds(branches: readonly BranchLike[]): string[] {
  return [...new Set(branches.flatMap((b) => (b.kind ? [b.kind] : [])))];
}

/** Picking a kind clears a branch that does not belong to it, and the other way round. */
export function pickKind(filter: BranchFilter, kind: string | null, branches: readonly BranchLike[]): BranchFilter {
  const branch = branches.find((b) => b.id === filter.branchId);
  return { kind, branchId: kind && branch && branch.kind !== kind ? null : filter.branchId };
}

export function pickBranch(branchId: string | null): BranchFilter {
  return { branchId, kind: null };
}

/** The branches the filter leaves in view. */
export function visibleBranches<T extends BranchLike>(branches: readonly T[], filter: BranchFilter): T[] {
  return branches.filter((b) => (!filter.branchId || b.id === filter.branchId) && (!filter.kind || b.kind === filter.kind));
}

/** Sessions at a branch the filter leaves in view; sessions without a branch stay in unless a filter is set. */
export function filterByBranch<T extends { location_id?: string | null }>(
  sessions: readonly T[],
  branches: readonly BranchLike[],
  filter: BranchFilter,
): T[] {
  if (!filter.branchId && !filter.kind) return [...sessions];
  const ids = new Set(visibleBranches(branches, filter).map((b) => b.id));
  return sessions.filter((s) => !!s.location_id && ids.has(s.location_id));
}
