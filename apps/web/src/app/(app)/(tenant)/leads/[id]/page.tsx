import { Container } from "@/components/layout/container";

import { LeadBody } from "./lead-body";

export default async function LeadPage({ params }: PageProps<"/leads/[id]">) {
  const { id } = await params;
  return (
    <Container as="main" size="settings" className="enter flex flex-1 flex-col gap-6 py-8 sm:py-10">
      <LeadBody id={id} />
    </Container>
  );
}
