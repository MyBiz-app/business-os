"use client";

import { ExternalLink, SendHorizontal, X } from "lucide-react";
import { useTranslations } from "next-intl";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useRef, useState } from "react";

import { agentForPath, bubbleHidden, fanFor } from "@/lib/ai-bubble";

import { type ChatError, type Conversation, decideAction, sendMessage, startConversation } from "../ai/actions";
import { AgentAvatar } from "../ai/agent-avatar";
import { ActionCard } from "../ai/chat-panel";
import type { Agent } from "../ai/types";
import { loadBubble } from "./actions";
import { useScreenLabel } from "./screen-context";

const LONG_PRESS_MS = 500;
/** What the AI is told about the screen is capped by the API. */
const CONTEXT_MAX = 200;

/** The face on the round button: a change of agent fades one picture into the next. */
function Crossfade({ agent }: { agent: Agent }) {
  const [state, setState] = useState<{ current: Agent; previous: Agent | null }>({ current: agent, previous: null });
  if (state.current.key !== agent.key) setState({ current: agent, previous: state.current });
  else if (state.current !== agent) setState({ current: agent, previous: state.previous });
  useEffect(() => {
    if (!state.previous) return;
    const timer = window.setTimeout(() => setState((s) => ({ ...s, previous: null })), 500);
    return () => window.clearTimeout(timer);
  }, [state.previous]);
  return (
    <>
      {state.previous && (
        <span key={state.previous.key} className="ai-fade-out absolute inset-0">
          <AgentAvatar agent={state.previous} className="size-full" />
        </span>
      )}
      <span key={state.current.key} className={`absolute inset-0 ${state.previous ? "ai-fade-in" : ""}`}>
        <AgentAvatar agent={state.current} className="size-full" />
      </span>
    </>
  );
}

/** A small AI chat on every CRM screen: the agent follows the screen, and knows what the screen shows. */
export function AiBubble() {
  const t = useTranslations("aiBubble");
  const tTeam = useTranslations("aiTeam");
  const tAssistant = useTranslations("assistant");
  const path = usePathname();
  const label = useScreenLabel();
  const [team, setTeam] = useState<{ agents: Agent[]; enabled: boolean } | null>(null);
  const [open, setOpen] = useState(false);
  const [fan, setFan] = useState(false);
  const [picked, setPicked] = useState<{ key: string; path: string } | null>(null);
  const [chats, setChats] = useState<Record<string, { conversation: Conversation; context: string }>>({});
  const [waitingFor, setWaitingFor] = useState<string | null>(null);
  const [error, setError] = useState<ChatError | null>(null);
  const [text, setText] = useState("");
  const wrapper = useRef<HTMLDivElement>(null);
  const button = useRef<HTMLButtonElement>(null);
  const field = useRef<HTMLTextAreaElement>(null);
  const end = useRef<HTMLDivElement>(null);
  const pressTimer = useRef<number | null>(null);
  const pressed = useRef(false);
  const touch = useRef(false);
  // The chat an agent hands over to starts with the last exchange of the one before.
  const carry = useRef<string | null>(null);

  useEffect(() => {
    let live = true;
    loadBubble()
      .then((loaded) => live && setTeam(loaded))
      .catch(() => {});
    return () => {
      live = false;
    };
  }, []);

  const available = (team?.agents ?? []).filter((a) => a.state === "active");
  const keys = available.map((a) => a.key);
  const routeKey = agentForPath(path);
  const defaultKey = keys.includes(routeKey) ? routeKey : "chief";
  // A pick holds on one screen; on another screen the bubble follows that screen again.
  const pickedKey = picked?.path === path ? picked.key : null;
  const shown = available.find((a) => a.key === (pickedKey ?? defaultKey)) ?? available.find((a) => a.key === "chief") ?? available[0];
  const context = (label ?? path).slice(0, CONTEXT_MAX);
  const chat = shown ? chats[shown.key] : undefined;
  const turns = chat?.conversation.turns ?? [];
  const busy = waitingFor !== null;

  useEffect(() => end.current?.scrollIntoView({ block: "end", behavior: "smooth" }), [turns.length, waitingFor, open]);
  useEffect(() => {
    if (open) field.current?.focus();
  }, [open, shown?.key]);
  useEffect(() => {
    if (!open && !fan) return;
    const onKey = (event: KeyboardEvent) => {
      if (event.key !== "Escape") return;
      setOpen(false);
      setFan(false);
      button.current?.focus();
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [open, fan]);

  if (!team || !shown || bubbleHidden(path)) return null;

  const fanAgents = fanFor(path, keys).flatMap((key) => available.find((a) => a.key === key) ?? []);

  function choose(agent: Agent) {
    setPicked({ key: agent.key, path });
    setFan(false);
    setError(null);
    setOpen(true);
  }

  async function submit(value: string) {
    const question = value.trim();
    if (!question || busy || !team?.enabled || !shown) return;
    setText("");
    setError(null);
    setWaitingFor(question);
    try {
      let current = chats[shown.key];
      // A chat keeps the screen it started on, so a new screen starts a new chat that carries the last exchange.
      if (!current || current.context !== context) {
        const previous = current?.conversation.turns.length ? current.conversation.id : carry.current;
        const started = await startConversation({ agentKey: shown.key, locationIds: null, handoffFrom: previous, pageContext: context });
        carry.current = null;
        if (!started.conversation) {
          setError(started.error ?? "generic");
          return;
        }
        current = { conversation: started.conversation, context };
      }
      const sent = await sendMessage(current.conversation.id, question);
      if (sent.conversation) setChats((all) => ({ ...all, [shown.key]: { conversation: sent.conversation!, context } }));
      else setError(sent.error ?? "generic");
    } catch {
      setError("generic");
    } finally {
      setWaitingFor(null);
    }
  }

  async function decide(actionId: string, decision: "confirm" | "reject") {
    if (!chat) return;
    const result = await decideAction(chat.conversation.id, actionId, decision);
    if (result.conversation) setChats((all) => ({ ...all, [shown!.key]: { conversation: result.conversation!, context: chat.context } }));
  }

  function handoff(agentKey: string) {
    const target = available.find((a) => a.key === agentKey);
    if (!target) return;
    carry.current = turns.length ? chat!.conversation.id : null;
    setPicked({ key: target.key, path });
  }

  const suggestions = turns.length === 0 && !busy ? (["s1", "s2", "s3"] as const).map((k) => tTeam(`suggestions.${shown.builtin ? shown.key : "custom"}.${k}` as "suggestions.chief.s1")) : [];

  return (
    <div
      ref={wrapper}
      className="fixed bottom-5 end-5 z-40 print:hidden"
      onPointerLeave={(event) => event.pointerType === "mouse" && setFan(false)}
      onBlur={(event) => !wrapper.current?.contains(event.relatedTarget as Node | null) && setFan(false)}
    >
      {open && (
        <section role="dialog" aria-label={tTeam("chatWith", { name: shown.name })} className="ai-panel-in absolute bottom-[4.5rem] end-0 flex h-[34rem] max-h-[calc(100dvh-8rem)] w-[25rem] max-w-[calc(100vw-2.5rem)] flex-col overflow-hidden rounded-3xl border border-border bg-surface shadow-2xl">
          <header className="flex items-center gap-3 border-b border-border p-3">
            <AgentAvatar agent={shown} className="size-10 shrink-0" />
            <div className="min-w-0 flex-1">
              <h2 className="truncate font-semibold" dir="auto">
                {shown.name}
              </h2>
              <p className="truncate text-xs text-muted" dir="auto">
                {label ? t("about", { what: label }) : shown.role_title}
              </p>
            </div>
            <Link href={`/ai?agent=${encodeURIComponent(shown.key)}`} className="btn-secondary inline-flex items-center gap-1.5 px-2.5 py-1.5 text-xs" onClick={() => setOpen(false)}>
              <ExternalLink aria-hidden="true" className="size-3.5" />
              {t("openFull")}
            </Link>
            <button type="button" onClick={() => setOpen(false)} className="btn-secondary p-1.5" aria-label={t("close")}>
              <X aria-hidden="true" className="size-4" />
            </button>
          </header>

          <div className="flex flex-1 flex-col gap-3 overflow-y-auto p-3" aria-live="polite">
            {turns.length === 0 && !busy && (
              <div className="m-auto flex max-w-xs flex-col items-center gap-2 text-center">
                <AgentAvatar agent={shown} className="size-16" />
                <p className="font-semibold" dir="auto">
                  {tTeam("greeting", { name: shown.name })}
                </p>
              </div>
            )}
            <ol className="flex flex-col gap-3">
              {turns.map((turn, index) => (
                <li key={index} className={`flex flex-col gap-2 ${turn.role === "user" ? "items-end" : "items-start"}`}>
                  <span className="sr-only">{turn.role === "user" ? tAssistant("you") : shown.name}</span>
                  {turn.role === "user" ? (
                    <p className="max-w-[85%] whitespace-pre-wrap rounded-2xl bg-primary px-3 py-2 text-sm text-on-primary" dir="auto">
                      {turn.text}
                    </p>
                  ) : (
                    <div className="flex min-w-0 max-w-[92%] flex-col gap-2">
                      <p className="whitespace-pre-wrap rounded-2xl bg-background px-3 py-2 text-sm" dir="auto">
                        {turn.text || tAssistant("noAnswer")}
                      </p>
                      {turn.pending_actions.map((action) => (
                        <ActionCard key={action.id} action={action} onDecide={decide} />
                      ))}
                      {turn.suggestions.map((suggestion) => {
                        const target = available.find((a) => a.key === suggestion.agent_key);
                        return (
                          <button key={suggestion.agent_key} type="button" onClick={() => handoff(suggestion.agent_key)} className="btn-plain flex flex-col items-start gap-1 rounded-xl border border-primary/40 bg-background p-2.5 text-start text-sm hover:bg-surface">
                            <span className="font-medium" dir="auto">
                              {tTeam("handoff", { name: target?.name ?? suggestion.agent_key })}
                            </span>
                            <span className="text-muted" dir="auto">
                              {suggestion.reason}
                            </span>
                          </button>
                        );
                      })}
                    </div>
                  )}
                </li>
              ))}
              {waitingFor !== null && (
                <>
                  <li className="flex justify-end">
                    <p className="max-w-[85%] whitespace-pre-wrap rounded-2xl bg-primary px-3 py-2 text-sm text-on-primary" dir="auto">
                      {waitingFor}
                    </p>
                  </li>
                  <li role="status" className="flex items-center gap-2 text-sm text-muted">
                    <AgentAvatar agent={shown} className="size-6" />
                    {tTeam("thinking", { name: shown.name })}
                  </li>
                </>
              )}
            </ol>
            <div ref={end} />
          </div>

          <div className="flex flex-col gap-2 border-t border-border p-3">
            {!team.enabled && (
              <p role="status" className="text-sm text-muted">
                {tAssistant("notConfigured")}
              </p>
            )}
            {error && (
              <p role="alert" className="text-sm text-danger">
                {tAssistant(`errors.${error}`)}
              </p>
            )}
            {suggestions.length > 0 && team.enabled && (
              <div className="flex flex-wrap gap-1.5">
                {suggestions.map((suggestion) => (
                  <button key={suggestion} type="button" onClick={() => submit(suggestion)} className="btn-plain rounded-full border border-border bg-background px-2.5 py-1 text-xs hover:bg-surface" dir="auto">
                    {suggestion}
                  </button>
                ))}
              </div>
            )}
            <form
              className="flex items-end gap-2"
              onSubmit={(event) => {
                event.preventDefault();
                void submit(text);
              }}
            >
              <label className="sr-only" htmlFor="ai-bubble-question">
                {tAssistant("question")}
              </label>
              <textarea
                id="ai-bubble-question"
                ref={field}
                value={text}
                onChange={(event) => setText(event.target.value)}
                onKeyDown={(event) => {
                  if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing) {
                    event.preventDefault();
                    void submit(text);
                  }
                }}
                rows={2}
                maxLength={2000}
                disabled={!team.enabled}
                placeholder={tTeam("placeholder", { name: shown.name })}
                className="min-h-[2.75rem] flex-1 resize-none rounded-xl border border-border bg-background px-3 py-2 text-sm"
                dir="auto"
              />
              <button type="submit" disabled={busy || !team.enabled || !text.trim()} className="btn-primary p-2.5 disabled:opacity-50" aria-label={tAssistant("send")}>
                <SendHorizontal aria-hidden="true" className="size-5 rtl:-scale-x-100" />
              </button>
            </form>
          </div>
        </section>
      )}

      <button
        ref={button}
        type="button"
        aria-expanded={open}
        aria-haspopup="dialog"
        aria-label={t("open", { name: shown.name })}
        title={t("open", { name: shown.name })}
        className="btn-plain ai-bubble relative block size-14 rounded-full shadow-lg ring-2 ring-offset-2 ring-offset-background transition-transform hover:scale-105 focus-visible:outline-2 focus-visible:outline-offset-4"
        style={{ ["--tw-ring-color" as string]: shown.color }}
        onPointerEnter={(event) => event.pointerType === "mouse" && setFan(true)}
        onPointerDown={(event) => {
          touch.current = event.pointerType !== "mouse";
          pressed.current = false;
          pressTimer.current = window.setTimeout(() => {
            pressed.current = true;
            setFan(true);
          }, LONG_PRESS_MS);
        }}
        onPointerUp={() => pressTimer.current && window.clearTimeout(pressTimer.current)}
        onPointerCancel={() => pressTimer.current && window.clearTimeout(pressTimer.current)}
        onFocus={(event) => event.currentTarget.matches(":focus-visible") && setFan(true)}
        onClick={() => {
          // A long press already opened the fan. On a touch screen the first tap opens the fan, the next one the chat.
          if (pressed.current) {
            pressed.current = false;
            return;
          }
          if (touch.current && !fan && !open) {
            setFan(true);
            return;
          }
          setFan(false);
          setOpen((value) => !value);
        }}
      >
        <Crossfade agent={shown} />
      </button>

      {fan && !open && (
        <ul aria-label={t("fan")} className="absolute bottom-full end-0 mb-3 flex flex-col-reverse items-center gap-2">
          {fanAgents.map((agent, index) => (
            <li key={agent.key} className="ai-fan-in" style={{ animationDelay: `${index * 40}ms` }}>
              <button
                type="button"
                onClick={() => choose(agent)}
                aria-label={`${agent.name}, ${agent.role_title}`}
                title={`${agent.name} · ${agent.role_title}`}
                className="btn-plain block size-11 rounded-full shadow-md ring-2 ring-offset-2 ring-offset-background transition-transform hover:scale-110"
                style={{ ["--tw-ring-color" as string]: agent.color }}
              >
                <AgentAvatar agent={agent} className="size-full" />
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
