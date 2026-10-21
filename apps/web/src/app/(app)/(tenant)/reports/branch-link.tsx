import { openBranchDashboard } from "./actions";
import { Button } from "@/components/ui/button";

/** A branch name that opens the dashboard for that branch. */
export function BranchLink({ id, children }: { id: string; children: React.ReactNode }) {
  return (
    <form action={openBranchDashboard} className="contents">
      <input type="hidden" name="branch_id" value={id} />
      <Button variant="plain" type="submit" className="min-w-0 truncate text-start underline-offset-4 hover:text-primary-ink hover:underline">
        {children}
      </Button>
    </form>
  );
}
