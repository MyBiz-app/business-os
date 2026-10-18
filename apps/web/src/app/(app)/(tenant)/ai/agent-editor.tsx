"use client";

import { Trash2 } from "lucide-react";
import { useLocale, useTranslations } from "next-intl";
import { useId, useState } from "react";

import { Field, SelectField, TextAreaField } from "@/components/form/field";
import { Modal } from "@/components/ui/modal";

import { type AgentChange, type AgentError, type AgentResult, deleteAgent, saveAgent, uploadAgentAvatar } from "./actions";
import { ColorChoice, DomainChecks, FaceChooser, type Face, RoleChecks, type RoleOption } from "./agent-fields";
import type { Tone } from "@/lib/agent-templates";
import { type Branch, ScopePicker } from "./scope-picker";
import type { Agent } from "./types";

const TIERS = ["fast", "standard", "strong"] as const;
const TONES: Tone[] = ["friendly", "formal", "short"];

type Props = { agent: Agent; branches: Branch[]; roles: RoleOption[]; onClose: () => void; onSaved: (agent: Agent) => void; onDeleted: (key: string) => void };

/** An agent's card: everything the business can change about it. Built-in agents keep their defaults for whatever is left alone; a custom one can also be removed. */
export function AgentEditor({ agent, branches, roles, onClose, onSaved, onDeleted }: Props) {
  const t = useTranslations("aiTeam.wizard");
  const tEdit = useTranslations("aiTeam.edit");
  const locale = useLocale();
  const formId = useId();
  const [name, setName] = useState(agent.name);
  const [roleTitle, setRoleTitle] = useState(agent.role_title);
  const [color, setColor] = useState(agent.color);
  const [topic, setTopic] = useState(agent.topic);
  const [instructions, setInstructions] = useState(agent.instructions ?? "");
  const [tone, setTone] = useState<Tone>(agent.tone);
  const [domains, setDomains] = useState<string[]>(agent.tool_domains ?? []);
  const [scope, setScope] = useState<string[] | null>(agent.location_scope === "locations" ? (agent.location_ids ?? []) : null);
  const [allowed, setAllowed] = useState<string[]>(agent.allowed_roles ?? []);
  const [tier, setTier] = useState<(typeof TIERS)[number]>(agent.model_tier ?? "fast");
  const [enabled, setEnabled] = useState(agent.enabled);
  const [face, setFace] = useState<Face>({ preset: null, file: null, preview: null });
  const [touched, setTouched] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<AgentError | null>(null);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const number = new Intl.NumberFormat(locale, { maximumFractionDigits: 1 });

  async function save(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      // Only what was changed is sent, so a built-in agent keeps following the catalog for the rest.
      const next: AgentChange = {
        name: name.trim() || null,
        role_title: roleTitle.trim() || null,
        color,
        topic: topic.trim() || null,
        instructions: instructions.trim() || null,
        tone,
        tool_domains: domains,
        allowed_roles: allowed,
        location_scope: scope ? "locations" : "all",
        location_ids: scope ?? [],
        model_tier: tier,
        enabled,
      };
      const before: AgentChange = {
        name: agent.name,
        role_title: agent.role_title,
        color: agent.color,
        topic: agent.topic || null,
        instructions: agent.instructions || null,
        tone: agent.tone,
        tool_domains: agent.tool_domains ?? [],
        allowed_roles: agent.allowed_roles ?? [],
        location_scope: agent.location_scope === "locations" ? "locations" : "all",
        location_ids: agent.location_scope === "locations" ? (agent.location_ids ?? []) : [],
        model_tier: agent.model_tier ?? "fast",
        enabled: agent.enabled,
      };
      const change: AgentChange = {};
      for (const key of Object.keys(next) as (keyof AgentChange)[]) {
        if (JSON.stringify(next[key]) !== JSON.stringify(before[key])) Object.assign(change, { [key]: next[key] });
      }
      // A gallery face replaces any picture; "reset" (touched, nothing chosen) goes back to the default face.
      if (face.preset) change.avatar_preset = face.preset;
      else if (touched && !face.file) change.avatar_preset = null;
      let saved: AgentResult = Object.keys(change).length ? await saveAgent(agent.key, change) : { agent };
      if (saved.agent && face.file) {
        const data = new FormData();
        data.set("avatar", face.file);
        saved = await uploadAgentAvatar(agent.key, data);
      }
      if (!saved.agent) return setError(saved.error ?? "generic");
      onSaved(saved.agent);
    } finally {
      setBusy(false);
    }
  }

  async function remove() {
    setBusy(true);
    await deleteAgent(agent.key);
    onDeleted(agent.key);
  }

  return (
    <Modal
      title={tEdit("title", { name: agent.name })}
      description={tEdit("usage", { used: number.format(agent.credits_used_month ?? 0) })}
      size="md"
      onClose={onClose}
      footer={
        <>
          <button type="button" onClick={onClose} className="btn-secondary px-4 py-2 text-sm">
            {tEdit("cancel")}
          </button>
          <button type="submit" form={formId} disabled={busy} className="btn-primary px-4 py-2 text-sm">
            {tEdit("save")}
          </button>
        </>
      }
    >
      <form id={formId} onSubmit={save}>
        <div className="flex flex-col gap-5">
          <label className="flex cursor-pointer items-center gap-3 rounded-xl bg-surface p-3">
            <input type="checkbox" checked={enabled} onChange={(e) => setEnabled(e.target.checked)} className="size-4 accent-[var(--primary)]" />
            <span className="text-sm font-medium">{tEdit("enabled")}</span>
          </label>
          <Field label={t("name")} value={name} onChange={(e) => setName(e.target.value)} maxLength={60} required />
          <Field label={t("roleTitle")} value={roleTitle} onChange={(e) => setRoleTitle(e.target.value)} maxLength={80} />
          <Field label={tEdit("topic")} value={topic} onChange={(e) => setTopic(e.target.value)} maxLength={200} />
          <ColorChoice value={color} onChange={setColor} />
          <FaceChooser
            agent={agent}
            face={face}
            onChange={(next) => {
              setTouched(true);
              setFace(next);
            }}
          />
          <TextAreaField label={tEdit("instructions")} value={instructions} onChange={(e) => setInstructions(e.target.value)} rows={7} maxLength={4000} />
          <SelectField label={t("tone")} value={tone} onChange={(e) => setTone(e.target.value as Tone)} options={TONES.map((x) => ({ value: x, label: t(`tones.${x}`) }))} />
          <SelectField label={tEdit("tier")} value={tier} onChange={(e) => setTier(e.target.value as (typeof TIERS)[number])} options={TIERS.map((x) => ({ value: x, label: tEdit(`tiers.${x}`) }))} />
          {!agent.builtin || (agent.tool_domains?.length ?? 0) > 0 ? <DomainChecks value={domains} onChange={setDomains} /> : null}
          {branches.length > 1 && (
            <div className="flex flex-wrap items-center gap-3">
              <span className="text-sm font-medium">{t("branches")}</span>
              <ScopePicker branches={branches} value={scope} onChange={setScope} />
            </div>
          )}
          <RoleChecks value={allowed} custom={roles} onChange={setAllowed} />
          {!agent.builtin && (
            <div className="rounded-xl border border-danger/40 p-3">
              {confirmDelete ? (
                <div className="flex flex-wrap items-center gap-2">
                  <p className="flex-1 text-sm">{tEdit("deleteAsk", { name: agent.name })}</p>
                  <button type="button" onClick={remove} disabled={busy} className="btn-secondary px-3 py-1.5 text-sm text-danger">
                    {tEdit("deleteYes")}
                  </button>
                  <button type="button" onClick={() => setConfirmDelete(false)} className="btn-ghost px-3 py-1.5 text-sm">
                    {tEdit("cancel")}
                  </button>
                </div>
              ) : (
                <button type="button" onClick={() => setConfirmDelete(true)} className="btn-ghost text-sm text-danger">
                  <Trash2 aria-hidden="true" className="size-4" />
                  {tEdit("delete")}
                </button>
              )}
            </div>
          )}
          {error && (
            <p role="alert" className="rounded-xl border border-danger/50 bg-danger/10 p-3 text-sm">
              {t(`errors.${error}` as "errors.generic", { limit: 0 })}
            </p>
          )}
        </div>
      </form>
    </Modal>
  );
}
