import { Container } from "@/components/layout/container";

import { ClientBody } from "./client-body";

export default async function ClientPage({ params }: PageProps<"/clients/[id]">) {
  const { id } = await params;
  return (
    <Container as="main" size="full" className="enter flex flex-1 flex-col gap-6 py-8 sm:py-10">
      <ClientBody id={id} />
    </Container>
  );
}
