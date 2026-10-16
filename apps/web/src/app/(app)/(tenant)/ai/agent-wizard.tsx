"use client";

import { ArrowLeft, ArrowRight, Check, Send, X } from "lucide-react";
import { useTranslations } from "next-intl";
import { useEffect, useRef, useState } from "react";

import { Field, SelectField, TextAreaField } from "@/components/form/field";

import {
  type AgentError,
  type Conversation,
  createAgentDraft,
  deleteAgent,
  saveAgent,
  sendMessage,
  startConversation,
  uploadAgentAvatar,
} from "./actions";
import { AgentAvatar } from "./agent-avatar";
import { ColorChoice, DomainChecks, FaceChooser, type Face, RoleChecks, type RoleOption } from "./agent-fields";
import { composeInstructions, TEMPLATES, type Tone } from "@/lib/agent-templates";
import { type Branch, ScopePicker } from "./scope-picker";
import type { Agent } from "./types";

const STEPS = ["topic", "identity", "role", "data", "access", "trial"] as const;
const TONES: Tone[] = ["friendly", "formal", "short"];

type Props = { branches: Branch[]; roles: RoleOption[]; limit: number; count: number; onClose: () => void; onDone: (agent: Agent) => void };

/** Hiring a new agent in six steps: what it is for, who it is, what it does, what it may see, who may talk to it, and a trial chat before anything is saved into the team. */
export function AgentWizard({ branches, roles, limit, count, onClose, onDone }: Props) {
  const t = useTranslations("aiTeam.wizard");
  const tTeam = useTranslations("aiTeam");
  const dialog = useRef<HTMLDialogElement>(null);
  const [step, setStep] = useState(0);
  const [template, setTemplate] = useState<(typeof TEMPLATES)[number]["key"] | null>(null);
  const [name, setName] = useState("");
  const [roleTitle, setRoleTitle] = useState("");
  const [color, setColor] = useState<string>("#7C3AED");
  const [face, setFace] = useState<Face>({ preset: null, file: null, preview: null });
  const [does, setDoes] = useState("");
  const [never, setNever] = useState("");
  const [knowledge, setKnowledge] = useState("");
  const [tone, setTone] = useState<Tone>("friendly");
  const [domains, setDomains] = useState<string[]>([]);
  const [scope, setScope] = useState<string[] | null>(null);
  const [allowed, setAllowed] = useState<string[]>(["owner", "manager"]);
  const [draft, setDraft] = useState<Agent | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<AgentError | null>(null);
  const [conversation, setConversation] = useState<Conversation | null>(null);
  const [waiting, setWaiting] = useState<string | null>(null);
  const [text, setText] = useState("");
  const done = useRef(false);

  useEffect(() => {
    const element = dialog.current;
    if (element && !element.open) element.showModal();
  }, []);

  const full = count >= limit;
  const valid = [template !== null, name.trim().length > 0, does.trim().length > 0, domains.length > 0, allowed.length > 0, true][step];
  const instructions = composeInstructions({ does, never, knowledge }, { does: t("labels.does"), never: t("labels.never"), knowledge: t("labels.knowledge") });

  function pick(key: (typeof TEMPLATES)[number]["key"]) {
    const found = TEMPLATES.find((x) => x.key === key);
    if (!found) return;
    setTemplate(key);
    setDomains([...found.domains]);
    setTone(found.tone);
    setColor(found.color);
    if (key !== "other") {
      setName((n) => n || t(`templates.${key}.name` as "templates.nutrition.name"));
      setRoleTitle((r) => r || t(`templates.${key}.role` as "templates.nutrition.role"));
      setDoes((d) => d || t(`templates.${key}.does` as "templates.nutrition.does"));
    }
  }

  const body = () => ({
    name: name.trim(),
    role_title: roleTitle.trim(),
    color,
    topic: roleTitle.trim(),
    instructions,
    tone,
    tool_domains: domains,
    allowed_roles: allowed,
    location_scope: scope ? ("locations" as const) : ("all" as const),
    location_ids: scope ?? [],
    // A picture uploaded on an earlier pass stays unless a gallery face replaces it.
    ...(face.preset || !draft?.avatar_url ? { avatar_preset: face.preset } : {}),
  });

  /** Before the trial the agent exists as a draft only managers can talk to; going back and forth just updates it. */
  async function toTrial() {
    setBusy(true);
    setError(null);
    try {
      let agent = draft;
      if (!agent) {
        const created = await createAgentDraft(body());
        if (!created.agent) return setError(created.error ?? "generic");
        agent = created.agent;
      } else {
        const saved = await saveAgent(agent.key, body());
        if (!saved.agent) return setError(saved.error ?? "generic");
        agent = saved.agent;
      }
      if (face.file) {
        const data = new FormData();
        data.set("avatar", face.file);
        const uploaded = await uploadAgentAvatar(agent.key, data);
        if (!uploaded.agent) return setError(uploaded.error ?? "generic");
        agent = uploaded.agent;
        setFace((f) => ({ ...f, file: null }));
      }
      setDraft(agent);
      setConversation(null);
      setStep(5);
    } finally {
      setBusy(false);
    }
  }

  async function ask(question: string) {
    if (!draft || !question.trim() || waiting) return;
    setText("");
    setWaiting(question);
    setError(null);
    try {
      let chat = conversation;
      if (!chat) {
        const started = await startConversation({ agentKey: draft.key, locationIds: null, pageContext: "agent-wizard" });
        if (!started.conversation) return setError("generic");
        chat = started.conversation;
      }
      const sent = await sendMessage(chat.id, question);
      if (sent.conversation) setConversation(sent.conversation);
      else setError("generic");
    } finally {
      setWaiting(null);
    }
  }

  async function finish() {
    if (!draft) return;
    setBusy(true);
    const saved = await saveAgent(draft.key, { draft: false });
    setBusy(false);
    if (!saved.agent) return setError(saved.error ?? "generic");
    done.current = true;
    onDone(saved.agent);
  }

  async function close() {
    // An unfinished draft is not kept: it would count against the plan's agents.
    if (draft && !done.current) await deleteAgent(draft.key);
    onClose();
  }

  const turns = conversation?.turns ?? [];
  const previewAgent = { key: draft?.key ?? "draft", name: name || "?", color, avatar_preset: face.preset, avatar_key: draft?.avatar_key ?? null, avatar_url: draft?.avatar_url ?? null };

  return (
    <dialog ref={dialog} onClose={close} aria-labelledby="wizard-title" className="m-auto max-h-[calc(100dvh-2rem)] w-[min(44rem,calc(100vw-2rem))] overflow-hidden rounded-3xl border border-border bg-background p-0 text-foreground backdrop:bg-black/50 backdrop:backdrop-blur-sm">
      <div className="flex max-h-[calc(100dvh-2rem)] flex-col">
        <header className="flex items-center gap-3 border-b border-border p-4">
          <div className="min-w-0 flex-1">
            <h2 id="wizard-title" className="font-semibold">
              {t("title")}
            </h2>
            <p className="text-sm text-muted" aria-live="polite">
              {t("stepOf", { step: step + 1, total: STEPS.length, name: t(`steps.${STEPS[step]}`) })}
            </p>
          </div>
          <button type="button" onClick={() => dialog.current?.close()} className="rounded-full p-2 hover:bg-surface" aria-label={tTeam("close")}>
            <X aria-hidden="true" className="size-5" />
          </button>
        </header>
        <div role="progressbar" aria-valuemin={1} aria-valuemax={STEPS.length} aria-valuenow={step + 1} aria-label={t("title")} className="h-1 bg-surface">
          <div className="h-full bg-primary transition-[width]" style={{ width: `${((step + 1) / STEPS.length) * 100}%` }} />
        </div>

        <div className="flex flex-1 flex-col gap-4 overflow-y-auto p-4 sm:p-6">
          {full && step === 0 && (
            <p role="alert" className="rounded-xl border border-warning/50 bg-warning/10 p-3 text-sm">
              {t("limitReached", { limit })}
            </p>
          )}
          {step === 0 && (
            <fieldset className="flex flex-col gap-3">
              <legend className="text-sm text-muted">{t("topicHint")}</legend>
              <div className="grid gap-2 sm:grid-cols-2">
                {TEMPLATES.map((item) => (
                  <label key={item.key} className={`flex cursor-pointer flex-col gap-1 rounded-2xl border p-3 has-[:focus-visible]:ring-2 has-[:focus-visible]:ring-primary ${template === item.key ? "border-primary bg-primary/5" : "border-border hover:bg-surface"}`}>
                    <input type="radio" name="template" className="sr-only" checked={template === item.key} onChange={() => pick(item.key)} />
                    <span className="font-medium" dir="auto">
                      {t(`templates.${item.key}.label` as "templates.nutrition.label")}
                    </span>
                    <span className="text-sm text-muted" dir="auto">
                      {t(`templates.${item.key}.blurb` as "templates.nutrition.blurb")}
                    </span>
                  </label>
                ))}
              </div>
            </fieldset>
          )}
          {step === 1 && (
            <>
              <Field label={t("name")} value={name} onChange={(e) => setName(e.target.value)} maxLength={60} required />
              <Field label={t("roleTitle")} value={roleTitle} onChange={(e) => setRoleTitle(e.target.value)} maxLength={80} />
              <ColorChoice value={color} onChange={setColor} />
              <FaceChooser agent={previewAgent} face={face} onChange={setFace} />
            </>
          )}
          {step === 2 && (
            <>
              <TextAreaField label={t("does")} value={does} onChange={(e) => setDoes(e.target.value)} rows={4} placeholder={t("doesPlaceholder")} required />
              <SelectField label={t("tone")} value={tone} onChange={(e) => setTone(e.target.value as Tone)} options={TONES.map((x) => ({ value: x, label: t(`tones.${x}`) }))} />
              <TextAreaField label={t("never")} value={never} onChange={(e) => setNever(e.target.value)} rows={3} placeholder={t("neverPlaceholder")} />
              <TextAreaField label={t("knowledge")} value={knowledge} onChange={(e) => setKnowledge(e.target.value)} rows={5} placeholder={t("knowledgePlaceholder")} />
              <p className={`text-xs ${instructions.length >= 3900 ? "text-danger" : "text-muted"}`}>{t("counter", { used: instructions.length, max: 4000 })}</p>
            </>
          )}
          {step === 3 && (
            <>
              <p className="text-sm text-muted">{t("dataHint")}</p>
              <DomainChecks value={domains} onChange={setDomains} />
              {branches.length > 1 && (
                <div className="flex flex-wrap items-center gap-3">
                  <span className="text-sm font-medium">{t("branches")}</span>
                  <ScopePicker branches={branches} value={scope} onChange={setScope} />
                </div>
              )}
            </>
          )}
          {step === 4 && (
            <>
              <p className="text-sm text-muted">{t("accessHint")}</p>
              <RoleChecks value={allowed} custom={roles} onChange={setAllowed} />
            </>
          )}
          {step === 5 && draft && (
            <div className="flex flex-col gap-3">
              <p className="text-sm text-muted">{t("trialHint")}</p>
              <div className="flex min-h-48 flex-col gap-3 rounded-2xl border border-border bg-surface p-3" aria-live="polite">
                {turns.length === 0 && !waiting && (
                  <div className="m-auto flex flex-col items-center gap-2 text-center">
                    <AgentAvatar agent={{ ...previewAgent, avatar_key: draft.avatar_key ?? null, avatar_url: draft.avatar_url ?? null }} className="size-14" />
                    <p className="text-sm">{tTeam("greeting", { name })}</p>
                  </div>
                )}
                {turns.map((turn, index) =>
                  turn.role === "user" ? (
                    <p key={index} className="max-w-[85%] self-end whitespace-pre-wrap rounded-2xl bg-primary px-3 py-2 text-sm text-on-primary" dir="auto">
                      {turn.text}
                    </p>
                  ) : (
                    <p key={index} className="max-w-[85%] self-start whitespace-pre-wrap rounded-2xl bg-background px-3 py-2 text-sm" dir="auto">
                      {turn.text}
                    </p>
                  ),
                )}
                {waiting && (
                  <>
                    <p className="max-w-[85%] self-end whitespace-pre-wrap rounded-2xl bg-primary px-3 py-2 text-sm text-on-primary" dir="auto">
                      {waiting}
                    </p>
                    <p className="text-sm text-muted">{tTeam("thinking", { name })}</p>
                  </>
                )}
              </div>
              <form
                onSubmit={(e) => {
                  e.preventDefault();
                  void ask(text);
                }}
                className="flex gap-2"
              >
                <input value={text} onChange={(e) => setText(e.target.value)} placeholder={tTeam("placeholder", { name })} aria-label={tTeam("placeholder", { name })} className="control min-w-0 flex-1 px-3 py-2" dir="auto" />
                <button type="submit" disabled={!text.trim() || waiting !== null} className="btn-primary px-3 py-2" aria-label={t("send")}>
                  <Send aria-hidden="true" className="size-4 rtl:-scale-x-100" />
                </button>
              </form>
            </div>
          )}
          {error && (
            <p role="alert" className="rounded-xl border border-danger/50 bg-danger/10 p-3 text-sm">
              {t(`errors.${error}` as "errors.generic", { limit })}
            </p>
          )}
        </div>

        <footer className="flex items-center justify-between gap-2 border-t border-border p-4">
          <button type="button" onClick={() => setStep((s) => s - 1)} disabled={step === 0 || busy} className="btn-secondary px-3 py-2 text-sm">
            <ArrowLeft aria-hidden="true" className="size-4 rtl:rotate-180" />
            {t("back")}
          </button>
          {step < 4 && (
            <button type="button" onClick={() => setStep((s) => s + 1)} disabled={!valid || full} className="btn-primary px-4 py-2 text-sm">
              {t("next")}
              <ArrowRight aria-hidden="true" className="size-4 rtl:rotate-180" />
            </button>
          )}
          {step === 4 && (
            <button type="button" onClick={toTrial} disabled={!valid || busy || full} className="btn-primary px-4 py-2 text-sm">
              {busy ? t("preparing") : t("tryIt")}
              <ArrowRight aria-hidden="true" className="size-4 rtl:rotate-180" />
            </button>
          )}
          {step === 5 && (
            <button type="button" onClick={finish} disabled={busy} className="btn-primary px-4 py-2 text-sm">
              <Check aria-hidden="true" className="size-4" />
              {t("hireNamed", { name })}
            </button>
          )}
        </footer>
      </div>
    </dialog>
  );
}
