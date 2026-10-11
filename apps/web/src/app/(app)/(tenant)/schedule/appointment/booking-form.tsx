"use client";

import { useTranslations } from "next-intl";
import { useActionState } from "react";

import { FormError } from "@/components/form/form-message";
import { SubmitButton } from "@/components/form/submit-button";

import { type AppointmentState, bookAppointment } from "./actions";

type Slot = { value: string; time: string; staff: string };
type Client = { id: string; name: string; detail: string };

/** Pick a free time and a client, then book. */
export function BookingForm({ serviceId, slots, clients }: { serviceId: string; slots: Slot[]; clients: Client[] }) {
  const t = useTranslations("appointments");
  const [state, action] = useActionState<AppointmentState, FormData>(bookAppointment.bind(null, serviceId), {});
  return (
    <form action={action} className="flex flex-col gap-5">
      <FormError message={state.error && t(`errors.${state.error}`)} />
      <fieldset className="flex flex-col gap-2">
        <legend className="mb-2 font-semibold">{t("chooseSlot")}</legend>
        <div className="enter-items grid grid-cols-3 gap-2 sm:grid-cols-5 lg:grid-cols-6">
          {slots.map((slot, index) => (
            <label
              key={slot.value}
              className="flex cursor-pointer flex-col items-center rounded-xl border border-border bg-surface px-2 py-2 text-center transition-colors hover:border-primary has-[:checked]:border-primary has-[:checked]:bg-primary has-[:checked]:text-on-primary"
            >
              <input type="radio" name="slot" value={slot.value} required defaultChecked={index === 0} className="sr-only" />
              <span className="font-semibold tabular-nums" dir="ltr">
                {slot.time}
              </span>
              <span className="truncate text-xs">{slot.staff}</span>
            </label>
          ))}
        </div>
      </fieldset>
      <fieldset className="flex flex-col gap-2">
        <legend className="mb-2 font-semibold">{t("client")}</legend>
        <ul className="flex flex-col divide-y divide-border rounded-xl border border-border">
          {clients.map((client, index) => (
            <li key={client.id}>
              <label className="flex cursor-pointer items-center gap-3 px-3 py-2.5 hover:bg-foreground/5">
                <input type="radio" name="client_id" value={client.id} required defaultChecked={index === 0} className="size-4 accent-primary" />
                <span className="font-medium" dir="auto">
                  {client.name}
                </span>
                <span className="text-sm text-muted" dir="ltr">
                  {client.detail}
                </span>
              </label>
            </li>
          ))}
        </ul>
      </fieldset>
      <div>
        <SubmitButton>{t("book")}</SubmitButton>
      </div>
    </form>
  );
}
