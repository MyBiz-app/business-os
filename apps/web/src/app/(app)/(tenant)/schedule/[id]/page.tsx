import { Container } from "@/components/layout/container";

import { SessionBody } from "./session-body";

export default async function SessionPage({ params, searchParams }: PageProps<"/schedule/[id]">) {
  const { id } = await params;
  return (
    <Container as="main" size="narrow" className="enter flex flex-1 flex-col gap-6 py-8 sm:py-10">
      <SessionBody id={id} query={await searchParams} />
    </Container>
  );
}
