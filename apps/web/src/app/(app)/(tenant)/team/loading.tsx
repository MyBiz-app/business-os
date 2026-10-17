import { CardsPageSkeleton } from "@/components/layout/page-skeletons";

/** Shown instantly while this page loads, at the same width as the page. */
export default function Loading() {
  return <CardsPageSkeleton size="default" />;
}
