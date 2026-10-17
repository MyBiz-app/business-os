import { CardsPageSkeleton } from "@/components/layout/page-skeletons";

/** Shown instantly while a team member's card loads. */
export default function Loading() {
  return <CardsPageSkeleton size="default" />;
}
