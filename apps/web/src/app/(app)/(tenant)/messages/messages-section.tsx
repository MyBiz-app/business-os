import { MessageCircle } from "lucide-react";
import { getLocale, getTranslations } from "next-intl/server";

import { unwrap } from "@/lib/api";
import { canWriteClients } from "@/lib/permissions";
import type { getTenant } from "@/lib/tenant";
import { whatsappLink } from "@/lib/whatsapp";

import { sendDirect } from "./actions";
import { DirectMessageForm } from "./direct-message";

type Props = {
  target: { client_id?: string; lead_id?: string };
  phone: string | null;
  path: string;
  context: Awaited<ReturnType<typeof getTenant>>;
  locked?: boolean;
};

/** Messages to one client or lead: open WhatsApp directly (free, from the user's own phone)
 * and, with the messaging module, send through MyBiz and see what was sent. */
export async function MessagesSection({ target, phone, path, context, locked = false }: Props) {
  const t = await getTranslations("messaging");
  const locale = await getLocale();
  const { tenant, api, scope } = context;
  const enabled = tenant.modules.includes("whatsapp");
  const link = phone ? whatsappLink(phone, tenant.time_zone) : null;
  if (!enabled && !link) return null;
  const log = enabled ? unwrap(await api.GET("/messages", { params: { ...scope, query: { ...target, limit: 20 } } })) : [];
  const when = new Intl.DateTimeFormat(locale, { dateStyle: "medium", timeStyle: "short", timeZone: tenant.time_zone });
  const canSend = enabled && !locked && canWriteClients(tenant) && !!phone;

  return (
    <section aria-labelledby="messages-heading" className="card flex flex-col gap-4 p-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 id="messages-heading" className="flex items-center gap-2 text-lg font-semibold">
          <MessageCircle aria-hidden="true" className="size-5 text-primary" />
          {t("sectionTitle")}
        </h2>
        {link && !locked && (
          <a href={link} target="_blank" rel="noreferrer" className="btn-secondary px-3 py-2 text-sm">
            {t("openWhatsApp")}
          </a>
        )}
      </div>
      {canSend && <DirectMessageForm action={sendDirect.bind(null, target, path)} />}
      {enabled &&
        (log.length === 0 ? (
          <p className="text-sm text-muted">{t("noMessages")}</p>
        ) : (
          <ol className="flex flex-col gap-2">
            {log.map((message) => (
              <li key={message.id} className="flex flex-col gap-1 rounded-xl bg-success/10 p-3">
                <p dir="auto" className="whitespace-pre-wrap text-sm">{message.body}</p>
                <p className="text-xs text-muted">
                  <time dateTime={message.created_at}>{when.format(new Date(message.created_at))}</time> ·{" "}
                  {t(`channels.${message.channel}`)} · {message.simulated ? t("simulatedSent") : t(`statuses.${message.status}`)}
                </p>
              </li>
            ))}
          </ol>
        ))}
    </section>
  );
}
