"use client";

import { useTranslations } from "next-intl";
import { useActionState } from "react";

import { FormError } from "@/components/form/form-message";
import { SubmitButton } from "@/components/form/submit-button";

import { type ReserveState, reserve } from "./actions";

type Slot = { value: string; time: string; room: string; price: string };
type Client = { id: string; name: string; detail: string };

/** Pick a free court and time, and the client, then reserve. */
export function ReserveForm({ serviceId, minutes, slots, clients }: { serviceId: string; minutes: number; slots: Slot[]; clients: Client[] }) {
  const t = useTranslations("resources");
  const [state, action] = useActionState<ReserveState, FormData>(reserve.bind(null, serviceId, minutes), {});
  const rooms = [...new Set(slots.map((slot) => slot.room))];
  return (
    <form action={action} className="flex flex-col gap-5">
      <FormError message={state.error && t(`errors.${state.error}`)} />
      {rooms.map((room) => (
        <fieldset key={room} className="flex flex-col gap-2">
          <legend className="mb-2 font-semibold">{room}</legend>
          <div className="grid grid-cols-3 gap-2 sm:grid-cols-5 lg:grid-cols-7">
            {slots
              .filter((slot) => slot.room === room)
              .map((slot) => (
                <label
                  key={slot.value}
                  className="flex cursor-pointer flex-col items-center rounded-xl border border-border bg-surface px-2 py-2 text-center transition-colors hover:border-primary has-[:checked]:border-primary has-[:checked]:bg-primary has-[:checked]:text-on-primary"
                >
                  <input
                    type="radio"
                    name="slot"
                    value={slot.value}
                    required
                    defaultChecked={slot.value === slots[0]?.value}
                    aria-label={`${room} ${slot.time}, ${slot.price}`}
                    className="sr-only"
                  />
                  <span className="font-semibold tabular-nums" dir="ltr">
                    {slot.time}
                  </span>
                </label>
              ))}
          </div>
        </fieldset>
      ))}
      <p className="text-sm text-muted">{t("price", { price: slots[0]?.price ?? "" })}</p>
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
        <SubmitButton>{t("reserve")}</SubmitButton>
      </div>
    </form>
  );
}
