"use client";

import { Send } from "lucide-react";
import { useTranslations } from "next-intl";
import { useState, useTransition } from "react";

import { FormError } from "@/components/form/form-message";

import { askConsoleAssistant, type ChatRole, type ChatTurn } from "./actions";

const ROLES: ChatRole[] = ["manager", "support", "health", "billing", "growth"];

/** MyBiz's own AI team: pick a helper, ask a question. The helpers only read and draft. */
export function ConsoleChat() {
  const t = useTranslations("platform.ai");
  const [role, setRole] = useState<ChatRole>("manager");
  const [chatId, setChatId] = useState<string | null>(null);
  const [turns, setTurns] = useState<ChatTurn[]>([]);
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
      if (result.id) setChatId(result.id);
      if (result.turns) setTurns(result.turns);
      if (result.error) setError(t(`errors.${result.error}` as "errors.generic"));
    });
  };

  return (
    <div className="flex flex-col gap-4">
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
