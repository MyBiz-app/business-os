import { openBranchDashboard } from "./actions";

/** A branch name that opens the dashboard for that branch. */
export function BranchLink({ id, children }: { id: string; children: React.ReactNode }) {
  return (
    <form action={openBranchDashboard} className="contents">
      <input type="hidden" name="branch_id" value={id} />
      <button type="submit" className="btn-plain min-w-0 truncate text-start underline-offset-4 hover:text-primary-ink hover:underline">
        {children}
      </button>
    </form>
  );
}
