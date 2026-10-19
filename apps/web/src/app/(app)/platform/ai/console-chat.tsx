"use client";

import { Send } from "lucide-react";
import { useLocale, useTranslations } from "next-intl";
import { useState, useTransition } from "react";

import { FormError } from "@/components/form/form-message";

import { askConsoleAssistant, openConsoleChat, type ChatOpened, type ChatRole, type ChatTurn } from "./actions";

const ROLES: ChatRole[] = ["manager", "support", "health", "billing", "growth"];

export type ChatListItem = { id: string; role: string; title: string | null; updatedAt: string };

/** MyBiz's own AI team: pick a helper, ask a question. The helpers only read and draft. The
 * conversations are saved, so a refresh or a later visit picks them up again. */
export function ConsoleChat({ chats: saved, initial }: { chats: ChatListItem[]; initial: ChatOpened | null }) {
  const t = useTranslations("platform.ai");
  const locale = useLocale();
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

  const stamp = new Intl.DateTimeFormat(locale, { dateStyle: "medium", timeStyle: "short" });

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
              {t(`roles.${chat.role as ChatRole}`)} · {chat.title ?? t("untitled")} · {stamp.format(new Date(chat.updatedAt))}
            </option>
          ))}
        </select>
        <button type="button" onClick={startNew} disabled={pending || chatId === null} className="btn-secondary px-3 py-2 text-sm">
          {t("newChat")}
        </button>
      </div>
      <div className="flex flex-wrap items-center gap-3">
        <label htmlFor="console-role" className="text-sm font-medium">
          {t("assistantRole")}
        </label>
        <select
          id="console-role"
          value={role}
          disabled={chatId !== null}
          onChange={(event) => setRole(event.target.value as ChatRole)}
          className="control px-3 py-2"
        >
          {ROLES.map((value) => (
            <option key={value} value={value}>
              {t(`roles.${value}`)}
            </option>
          ))}
        </select>
        <span className="text-sm text-muted">{t(`roleHints.${role}`)}</span>
      </div>
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
          placeholder={t("question")}
          className="control min-w-0 flex-1 px-3 py-2"
        />
        <button type="submit" disabled={pending || !text.trim()} className="btn-primary inline-flex items-center gap-2 px-4 py-2">
          <Send aria-hidden="true" className="size-4 rtl:-scale-x-100" />
          {t("send")}
        </button>
      </form>
    </div>
  );
}
