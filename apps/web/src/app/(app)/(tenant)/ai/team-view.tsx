"use client";

import { CircleHelp, FlaskConical, GitBranch, MessageCircle, Maximize2, Minimize2, RotateCcw, UserPlus } from "lucide-react";
import { useTranslations } from "next-intl";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useRef, useState } from "react";

import { PageHeader } from "@/components/layout/page-header";
import { SegmentedControl } from "@/components/segmented-control";
import { type Draft, draftOf, payloadOf } from "@/lib/ai-structure";

import {
  agentConversations,
  type ChatError,
  type Conversation,
  type ConversationSummary,
  decideAction,
  markAiTourSeen,
  openConversation,
  saveStructure,
  sendMessage,
  startConversation,
} from "./actions";
import { AgentDialog } from "./agent-dialog";
import { AgentAvatar } from "./agent-avatar";
import { AgentEditor } from "./agent-editor";
import type { RoleOption } from "./agent-fields";
import { AgentWizard } from "./agent-wizard";
import { AiTour } from "./ai-tour";
import { ChatPanel } from "./chat-panel";
import { type Branch } from "./scope-picker";
import { StructurePanel } from "./structure-panel";
import { TeamList } from "./team-list";
import { TeamMap } from "./team-map";
import { type MeterDetails, UsageMeter } from "./usage-meter";
import type { Agent, Meter, Team, Upsell } from "./types";

const MAP_WIDE_KEY = "ai-team-map-wide";

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
  /** The business's own roles, for choosing who may use an agent. */
  roles: RoleOption[];
  /** This person has already finished or skipped the first-time guide. */
  tourSeen?: boolean;
  /** An agent to open straight away (the floating bubble links here). */
  initialAgent?: string | null;
  /** The month's AI meter; the details (the usage window) only for those who manage the team. */
  meter: Meter;
  meterDetails: MeterDetails | null;
};

export function TeamView({ team, branches, enabled, demo, upsells, canAdd, timeZone, roles, tourSeen = true, initialAgent = null, meter, meterDetails }: Props) {
  const t = useTranslations("aiTeam");
  const tAssistant = useTranslations("assistant");
  const [selected, setSelected] = useState<string | null>(null);
  const [conversation, setConversation] = useState<Conversation | null>(null);
  const [history, setHistory] = useState<ConversationSummary[]>([]);
  const [scope, setScope] = useState<string[] | null>(null);
  const [view, setView] = useState<"map" | "list">("map");
  const [closedAgent, setClosedAgent] = useState<Agent | null>(null);
  const router = useRouter();
  const [touring, setTouring] = useState(!tourSeen);
  // The map can take the whole width while a chat stays open, shown as a small floating card.
  const [mapWide, setMapWide] = useState(false);
  const [wizard, setWizard] = useState(false);
  const [editing, setEditing] = useState<Agent | null>(null);
  const [waitingFor, setWaitingFor] = useState<string | null>(null);
  const [error, setError] = useState<ChatError | null>(null);
  // The chat whose last exchange the next new chat carries over (switching agent or branches).
  const carry = useRef<string | null>(null);
  const tourHelp = useRef<HTMLButtonElement>(null);

  // Structure editing: a working copy of the lines, teams and places, saved in one go.
  const saved = useMemo(() => draftOf(team.agents, team.teams ?? []), [team]);
  const [draft, setDraft] = useState<Draft | null>(null);
  const [savingStructure, setSavingStructure] = useState(false);
  const [structureError, setStructureError] = useState<string | null>(null);
  const structuring = draft !== null;

  function startEditing() {
    setSelected(null);
    setConversation(null);
    setView("map");
    setStructureError(null);
    setDraft(saved);
  }

  async function commitStructure() {
    if (!draft) return;
    setSavingStructure(true);
    setStructureError(null);
    const result = await saveStructure(payloadOf(draft, team.agents));
    setSavingStructure(false);
    if (result.error) {
      setStructureError(result.error);
      return;
    }
    setDraft(null);
    router.refresh();
  }

  function endTour() {
    setTouring(false);
    void markAiTourSeen();
    // The first guide opens by itself, so there is no opener to return to: land on the help button.
    window.setTimeout(() => tourHelp.current?.focus(), 0);
  }

  const agent = team.agents.find((a) => a.key === selected) ?? null;

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

  // Arriving from the floating chat opens that agent's chat.
  useEffect(() => {
    const target = initialAgent ? team.agents.find((a) => a.key === initialAgent) : null;
    if (!target) return;
    const timer = window.setTimeout(() => void open(target), 0);
    return () => window.clearTimeout(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps -- only on arrival
  }, []);

  const chatOpen = agent !== null;
  const wide = chatOpen && mapWide;

  // The last choice is remembered per browser.
  useEffect(() => {
    const timer = window.setTimeout(() => {
      try {
        setMapWide(window.localStorage.getItem(MAP_WIDE_KEY) === "1");
      } catch {
        // storage unavailable: start in the split view
      }
    }, 0);
    return () => window.clearTimeout(timer);
  }, []);

  function changeMapWide(next: boolean) {
    setMapWide(next);
    try {
      window.localStorage.setItem(MAP_WIDE_KEY, next ? "1" : "0");
    } catch {
      // not remembered
    }
  }

  // M toggles the big map while a chat is open (not while typing).
  useEffect(() => {
    if (!chatOpen) return;
    const onKey = (event: KeyboardEvent) => {
      if (event.key.toLowerCase() !== "m" || event.ctrlKey || event.metaKey || event.altKey) return;
      const target = event.target as HTMLElement | null;
      if (target?.closest("input, textarea, select, [contenteditable='true'], dialog[open]")) return;
      changeMapWide(!mapWide);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [chatOpen, mapWide]);

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

      <PageHeader
        title={t("title")}
        description={t("subtitle")}
        actions={
          <div className="flex items-center gap-2">
            <button ref={tourHelp} type="button" onClick={() => setTouring(true)} disabled={structuring} className="btn-secondary inline-flex h-11 items-center gap-2 px-4 text-sm">
              <CircleHelp aria-hidden="true" className="size-4" />
              {t("tour.help")}
            </button>
            {team.can_manage && (
              <button type="button" onClick={() => setWizard(true)} disabled={structuring} className="btn-primary inline-flex h-11 items-center gap-2 px-4 text-sm">
                <UserPlus aria-hidden="true" className="size-4" />
                {t("wizard.hire")}
              </button>
            )}
          </div>
        }
      />

      {/* One bar of a fixed height, so nothing jumps when the window changes size or the mode switches. */}
      <div role="toolbar" data-tour="ai-toolbar" aria-label={t("toolbar")} className="flex min-h-12 flex-wrap items-center justify-between gap-x-4 gap-y-2 rounded-2xl border border-border bg-surface px-4 py-2">
        {structuring ? (
          <>
            <p className="text-sm font-semibold">{t("structure.title")}</p>
            <div className="flex items-center gap-2">
              <button type="button" onClick={() => setDraft({ ...draft, pos: {} })} disabled={savingStructure} className="btn-secondary inline-flex h-9 items-center gap-1.5 px-3 text-sm">
                <RotateCcw aria-hidden="true" className="size-4" />
                {t("structure.relayout")}
              </button>
              <button type="button" onClick={() => setDraft(null)} disabled={savingStructure} className="btn-secondary h-9 px-3 text-sm">
                {t("structure.cancel")}
              </button>
              <button type="button" onClick={() => void commitStructure()} disabled={savingStructure} className="btn-primary h-9 px-3 text-sm">
                {savingStructure ? t("structure.saving") : t("structure.save")}
              </button>
            </div>
          </>
        ) : (
          <>
            <div data-tour="ai-usage">
              <UsageMeter meter={meter} details={meterDetails} />
            </div>
            <div className="flex items-center gap-2">
              <div className="hidden md:block">
                <SegmentedControl label={t("view")} value={view} onChange={setView} options={[{ value: "map", label: t("views.map") }, { value: "list", label: t("views.list") }]} />
              </div>
              {team.can_manage && (
                <button type="button" onClick={startEditing} className="btn-secondary inline-flex h-9 items-center gap-2 px-3 text-sm">
                  <GitBranch aria-hidden="true" className="size-4" />
                  {t("structure.edit")}
                </button>
              )}
            </div>
          </>
        )}
      </div>

      <div className="flex items-start gap-4">
        <div data-tour="ai-map" className={`relative min-w-0 motion-reduce:transition-none transition-[width] duration-700 ease-[cubic-bezier(0.22,1,0.36,1)] ${wide ? "w-full" : chatOpen ? "hidden w-full lg:block lg:w-72 lg:shrink-0 xl:w-80" : "w-full"}`}>
          {chatOpen && view === "map" && (
            <button
              type="button"
              onClick={() => changeMapWide(!wide)}
              aria-pressed={wide}
              aria-keyshortcuts="M"
              title={t(wide ? "map.shrink" : "map.expand")}
              aria-label={t(wide ? "map.shrink" : "map.expand")}
              className="btn-plain absolute end-3 top-3 z-20 hidden rounded-full border border-border bg-background/90 p-2 text-muted shadow-sm backdrop-blur hover:text-foreground focus-visible:outline-2 focus-visible:outline-primary md:block"
            >
              {wide ? <Minimize2 aria-hidden="true" className="size-4" /> : <Maximize2 aria-hidden="true" className="size-4" />}
            </button>
          )}
          {view === "map" ? (
            <>
              <div className="hidden md:block">
                <TeamMap agents={team.agents} selected={selected} compact={chatOpen && !wide} onPick={open} draft={draft ?? saved} editing={structuring} onDraft={setDraft} />
              </div>
              <div className="md:hidden">
                <TeamList agents={team.agents} selected={selected} onPick={open} />
              </div>
            </>
          ) : (
            <TeamList agents={team.agents} selected={selected} compact={chatOpen && !wide} onPick={open} />
          )}
        </div>
        {agent && (
          <div className={wide ? "hidden" : "contents"}>
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
            onEdit={team.can_manage ? () => setEditing(agent) : undefined}
            onBack={() => {
              setSelected(null);
              setConversation(null);
            }}
          />
          </div>
        )}
      </div>

      {draft && (
        <StructurePanel
          agents={team.agents}
          draft={draft}
          error={structureError}
          onChange={setDraft}
        />
      )}

      {agent && wide && (
        <button
          type="button"
          onClick={() => changeMapWide(false)}
          className="btn-plain ai-panel-in fixed bottom-4 end-4 z-40 flex max-w-[calc(100vw-2rem)] items-center gap-3 rounded-2xl border border-border bg-background p-3 text-start shadow-lg hover:bg-surface focus-visible:outline-2 focus-visible:outline-primary"
        >
          <span className="relative">
            <AgentAvatar agent={agent} className="size-10" />
            <MessageCircle aria-hidden="true" className="absolute -bottom-1 -end-1 size-4 rounded-full bg-primary p-0.5 text-on-primary" />
          </span>
          <span className="flex min-w-0 flex-col leading-tight">
            <span className="truncate text-sm font-semibold" dir="auto">
              {t("map.floatingChat", { name: agent.name })}
            </span>
            <span className="text-xs text-muted" role="status">
              {waitingFor ? t("map.floatingBusy") : t("map.floatingCount", { count: conversation?.turns.length ?? 0 })}
            </span>
          </span>
        </button>
      )}

      {touring && <AiTour agents={team.agents} canManage={team.can_manage} onClose={endTour} />}
      {closedAgent && (
        <AgentDialog
          agent={closedAgent}
          upsell={closedAgent.upsell_module ? (upsells[closedAgent.upsell_module] ?? null) : null}
          canAdd={canAdd}
          onEdit={team.can_manage && closedAgent.state === "disabled" ? () => {
            setEditing(closedAgent);
            setClosedAgent(null);
          } : undefined}
          onClose={() => setClosedAgent(null)}
        />
      )}
      {wizard && (
        <AgentWizard
          branches={branches}
          roles={roles}
          limit={team.custom_limit}
          count={team.custom_count}
          onClose={() => setWizard(false)}
          onDone={() => {
            setWizard(false);
            router.refresh();
          }}
        />
      )}
      {editing && (
        <AgentEditor
          key={editing.key}
          agent={editing}
          branches={branches}
          roles={roles}
          onClose={() => setEditing(null)}
          onSaved={() => {
            setEditing(null);
            router.refresh();
          }}
          onDeleted={(key) => {
            setEditing(null);
            if (selected === key) setSelected(null);
            router.refresh();
          }}
        />
      )}
    </div>
  );
}
