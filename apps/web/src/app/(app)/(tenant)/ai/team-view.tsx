"use client";

import { FlaskConical, LayoutGrid, Network } from "lucide-react";
import { useLocale, useTranslations } from "next-intl";
import { useRef, useState } from "react";

import {
  agentConversations,
  type ChatError,
  type Conversation,
  type ConversationSummary,
  decideAction,
  openConversation,
  sendMessage,
  startConversation,
} from "./actions";
import { AgentDialog } from "./agent-dialog";
import { ChatPanel } from "./chat-panel";
import { type Branch } from "./scope-picker";
import { TeamList } from "./team-list";
import { TeamMap } from "./team-map";
import type { Agent, Team, Upsell } from "./types";

type Props = {
  team: Team;
  branches: Branch[];
  /** An AI provider is set up on the server. */
  enabled: boolean;
  demo: boolean;
  upsells: Record<string, Upsell>;
  /** Whoever may change the plan sees "add to plan"; the others are told to ask the owner. */
  canAdd: boolean;
  timeZone: string;
};

export function TeamView({ team, branches, enabled, demo, upsells, canAdd, timeZone }: Props) {
  const t = useTranslations("aiTeam");
  const tAssistant = useTranslations("assistant");
  const locale = useLocale();
  const [selected, setSelected] = useState<string | null>(null);
  const [conversation, setConversation] = useState<Conversation | null>(null);
  const [history, setHistory] = useState<ConversationSummary[]>([]);
  const [scope, setScope] = useState<string[] | null>(null);
  const [view, setView] = useState<"map" | "list">("map");
  const [closedAgent, setClosedAgent] = useState<Agent | null>(null);
  const [waitingFor, setWaitingFor] = useState<string | null>(null);
  const [error, setError] = useState<ChatError | null>(null);
  // The chat whose last exchange the next new chat carries over (switching agent or branches).
  const carry = useRef<string | null>(null);

  const agent = team.agents.find((a) => a.key === selected) ?? null;
  const number = new Intl.NumberFormat(locale, { maximumFractionDigits: 1 });

  async function open(next: Agent) {
    if (next.state !== "active") {
      setClosedAgent(next);
      return;
    }
    if (next.key === selected) return;
    const previous = conversation?.turns.length ? conversation : null;
    setSelected(next.key);
    setError(null);
    setWaitingFor(null);
    try {
      const list = await agentConversations(next.key);
      setHistory(list);
      const latest = list.find((c) => !c.archived);
      if (latest && !previous) {
        const result = await openConversation(latest.id);
        setConversation(result.conversation ?? null);
        setScope(result.conversation?.location_ids ?? null);
        carry.current = null;
        return;
      }
    } catch {
      setHistory([]);
    }
    // No earlier chat to resume (or none could be loaded): a fresh one, created when the first question is sent.
    setConversation(null);
    carry.current = previous?.id ?? null;
  }

  async function send(text: string) {
    if (!agent) return;
    setError(null);
    setWaitingFor(text);
    try {
      let chat = conversation;
      if (!chat) {
        const started = await startConversation({ agentKey: agent.key, locationIds: scope, handoffFrom: carry.current, pageContext: "ai-team" });
        if (!started.conversation) {
          setError(started.error ?? "generic");
          return;
        }
        chat = started.conversation;
        carry.current = null;
        setConversation(chat);
      }
      const sent = await sendMessage(chat.id, text);
      if (sent.conversation) setConversation(sent.conversation);
      else setError(sent.error ?? "generic");
      setHistory(await agentConversations(agent.key));
    } catch {
      setError("generic");
    } finally {
      setWaitingFor(null);
    }
  }

  // A chat's branches are fixed when it starts, so a new choice starts a new chat that keeps the last exchange.
  function changeScope(ids: string[] | null) {
    setScope(ids);
    if (conversation) {
      carry.current = conversation.turns.length ? conversation.id : null;
      setConversation(null);
    }
  }

  async function decide(actionId: string, decision: "confirm" | "reject") {
    if (!conversation) return;
    const result = await decideAction(conversation.id, actionId, decision);
    if (result.conversation) setConversation(result.conversation);
  }

  async function openChat(id: string) {
    const result = await openConversation(id);
    if (result.conversation) {
      setConversation(result.conversation);
      setScope(result.conversation.location_ids ?? null);
      carry.current = null;
    }
  }

  function handoff(agentKey: string) {
    const target = team.agents.find((a) => a.key === agentKey);
    if (target) void open(target);
  }

  const chatOpen = agent !== null;

  return (
    <div className="flex flex-col gap-4">
      {demo && (
        <p role="note" className="flex items-start gap-2 rounded-2xl border border-warning/50 bg-warning/10 p-4 text-sm">
          <FlaskConical aria-hidden="true" className="mt-0.5 size-4 shrink-0" />
          {tAssistant("demoMode")}
        </p>
      )}
      {!enabled && (
        <p role="status" className="rounded-2xl border border-dashed border-border p-6 text-muted">
          {tAssistant("notConfigured")}
        </p>
      )}

      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="text-sm text-muted">{t("usage", { used: number.format(team.credits_used), included: number.format(team.credits_included) })}</p>
        <div role="group" aria-label={t("view")} className="hidden items-center gap-1 rounded-full border border-border p-1 md:flex">
          {(["map", "list"] as const).map((mode) => {
            const Icon = mode === "map" ? Network : LayoutGrid;
            return (
              <button key={mode} type="button" aria-pressed={view === mode} onClick={() => setView(mode)} className={`inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-sm ${view === mode ? "bg-primary text-on-primary" : "text-muted hover:text-foreground"}`}>
                <Icon aria-hidden="true" className="size-4" />
                {t(`views.${mode}`)}
              </button>
            );
          })}
        </div>
      </div>

      <div className="flex items-start gap-4">
        <div className={`min-w-0 transition-[width] duration-700 ease-[cubic-bezier(0.22,1,0.36,1)] ${chatOpen ? "hidden w-full lg:block lg:w-72 lg:shrink-0 xl:w-80" : "w-full"}`}>
          {view === "map" ? (
            <>
              <div className="hidden md:block">
                <TeamMap agents={team.agents} selected={selected} compact={chatOpen} onPick={open} />
              </div>
              <div className="md:hidden">
                <TeamList agents={team.agents} selected={selected} onPick={open} />
              </div>
            </>
          ) : (
            <TeamList agents={team.agents} selected={selected} compact={chatOpen} onPick={open} />
          )}
        </div>
        {agent && (
          <ChatPanel
            key={agent.key}
            agent={agent}
            agents={team.agents}
            conversation={conversation}
            waitingFor={waitingFor}
            error={error}
            enabled={enabled}
            branches={branches}
            scope={scope}
            history={history}
            timeZone={timeZone}
            onScope={changeScope}
            onSend={send}
            onSwitch={open}
            onNew={() => {
              carry.current = null;
              setConversation(null);
              setError(null);
            }}
            onOpen={openChat}
            onHandoff={handoff}
            onDecide={decide}
            onBack={() => {
              setSelected(null);
              setConversation(null);
            }}
          />
        )}
      </div>

      {closedAgent && <AgentDialog agent={closedAgent} upsell={closedAgent.upsell_module ? (upsells[closedAgent.upsell_module] ?? null) : null} canAdd={canAdd} onClose={() => setClosedAgent(null)} />}
    </div>
  );
}
