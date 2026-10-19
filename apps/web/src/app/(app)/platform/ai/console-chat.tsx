"use client";

import { Send } from "lucide-react";
import { useLocale, useTranslations } from "next-intl";
import { useState, useTransition } from "react";

import { FormError } from "@/components/form/form-message";
import { CollapsibleSection } from "@/components/ui/collapsible-section";

import { askConsoleAssistant, openConsoleChat, type ChatOpened, type ChatRole, type ChatTurn } from "./actions";
import { AgentEditor } from "./agent-editor";
import { AgentsMap, useAgentName, type AgentCard } from "./agents-map";

export type ChatListItem = { id: string; role: string; title: string | null; updatedAt: string };

/** MyBiz's own AI team: pick an agent on the map, ask a question. The agents only read and draft. The
 * conversations are saved, so a refresh or a later visit picks them up again. */
export function ConsoleChat({ agents, canEdit, chats: saved, initial }: { agents: AgentCard[]; canEdit: boolean; chats: ChatListItem[]; initial: ChatOpened | null }) {
  const t = useTranslations("platform.ai");
  const locale = useLocale();
  const nameOf = useAgentName();
  const [chats, setChats] = useState(saved);
  const [role, setRole] = useState<ChatRole>(initial?.role ?? "manager");
  const [chatId, setChatId] = useState<string | null>(initial?.id ?? null);
  const [turns, setTurns] = useState<ChatTurn[]>(initial?.turns ?? []);
  const [text, setText] = useState("");
  const [error, setError] = useState<string>();
  const [pending, start] = useTransition();

  const send = () => {
    const question = text.trim();
    if (!question) return;
    setText("");
    setError(undefined);
    setTurns((all) => [...all, { role: "user", text: question }]);
    start(async () => {
      const result = await askConsoleAssistant(chatId, role, question);
      if (result.id) {
        setChatId(result.id);
        setChats((all) =>
          all.some((chat) => chat.id === result.id)
            ? all
            : [{ id: result.id!, role, title: null, updatedAt: new Date().toISOString() }, ...all],
        );
      }
      if (result.turns) setTurns(result.turns);
      if (result.error) setError(t(`errors.${result.error}` as "errors.generic"));
    });
  };

  const open = (id: string) =>
    start(async () => {
      setError(undefined);
      const chat = await openConsoleChat(id);
      if (!chat) return setError(t("errors.generic"));
      setChatId(chat.id);
      setRole(chat.role);
      setTurns(chat.turns);
    });

  const startNew = () => {
    setChatId(null);
    setTurns([]);
    setError(undefined);
  };

  // Picking another agent starts a fresh conversation with it; the same agent keeps the open one.
  const pick = (agent: AgentCard) => {
    if (agent.key !== role) startNew();
    setRole(agent.key);
  };

  const stamp = new Intl.DateTimeFormat(locale, { dateStyle: "medium", timeStyle: "short" });
  const agent = agents.find((a) => a.key === role) ?? agents[0];
  const askable = !!agent && agent.ready && agent.enabled;

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center gap-3">
        <label htmlFor="console-history" className="text-sm font-medium">
          {t("history")}
        </label>
        <select
          id="console-history"
          value={chatId ?? ""}
          disabled={pending || chats.length === 0}
          onChange={(event) => event.target.value && open(event.target.value)}
          className="control min-w-0 max-w-full px-3 py-2"
        >
          {chatId === null && <option value="">{chats.length === 0 ? t("noHistory") : t("newChat")}</option>}
          {chats.map((chat) => (
            <option key={chat.id} value={chat.id}>
              {t(`agents.${chat.role as ChatRole}.name`)} · {chat.title ?? t("untitled")} · {stamp.format(new Date(chat.updatedAt))}
            </option>
          ))}
        </select>
        <button type="button" onClick={startNew} disabled={pending || chatId === null} className="btn-secondary px-3 py-2 text-sm">
          {t("newChat")}
        </button>
      </div>
      {agents.length > 0 && <AgentsMap agents={agents} selected={role} onPick={pick} />}
      {agent && (
        <div className="flex flex-col gap-1">
          <p className="font-semibold" dir="auto">
            {nameOf(agent)} <span className="font-normal text-muted">· {t(`agents.${agent.key}.title`)}</span>
          </p>
          <p className="text-sm text-muted">{t(`agents.${agent.key}.topic`)}</p>
          {!agent.ready && <p className="text-sm text-muted">{t("agentState.soonHint")}</p>}
          {agent.ready && !agent.enabled && <p className="text-sm text-muted">{t("agentState.offHint")}</p>}
        </div>
      )}
      {canEdit && agent && (
        <CollapsibleSection title={t("agentSettings")} variant="inline">
          <AgentEditor agent={agent} />
        </CollapsibleSection>
      )}
      <FormError message={error} />
      <ol aria-live="polite" className="flex max-h-[28rem] flex-col gap-3 overflow-y-auto">
        {turns.map((turn, index) => (
          <li
            key={index}
            dir="auto"
            className={`max-w-[90%] whitespace-pre-wrap rounded-2xl px-4 py-2.5 text-sm ${
              turn.role === "user" ? "self-end bg-primary/10" : "self-start border border-border"
            }`}
          >
            {turn.text}
          </li>
        ))}
        {pending && <li className="self-start text-sm text-muted">{t("thinking")}</li>}
      </ol>
      <form
        onSubmit={(event) => {
          event.preventDefault();
          send();
        }}
        className="flex gap-2"
      >
        <label htmlFor="console-question" className="sr-only">
          {t("question")}
        </label>
        <input
          id="console-question"
          value={text}
          onChange={(event) => setText(event.target.value)}
          maxLength={4000}
          disabled={!askable}
          placeholder={t("question")}
          className="control min-w-0 flex-1 px-3 py-2"
        />
        <button type="submit" disabled={pending || !askable || !text.trim()} className="btn-primary inline-flex items-center gap-2 px-4 py-2">
          <Send aria-hidden="true" className="size-4 rtl:-scale-x-100" />
          {t("send")}
        </button>
      </form>
    </div>
  );
}
