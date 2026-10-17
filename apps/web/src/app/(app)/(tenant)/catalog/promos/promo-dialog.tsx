"use client";

import { useRouter } from "next/navigation";
import type { ReactNode } from "react";

import { Modal } from "@/components/ui/modal";

/** The window of one discount code over the list. */
export function PromoDialog({ code, actions, children }: { code: string; actions: ReactNode; children: ReactNode }) {
  const router = useRouter();
  return (
    <Modal title={code} size="sm" onClose={() => router.back()} footer={actions}>
      {children}
    </Modal>
  );
}
