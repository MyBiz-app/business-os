"use client";

import { ChevronDown } from "lucide-react";
import { useEffect, useId, useMemo, useRef, useState, useSyncExternalStore } from "react";

import { SelectField, type SelectOption } from "./field";

const CONTROL = "control w-full min-w-0 px-3 py-2";

function subscribeCoarse(notify: () => void) {
  const query = window.matchMedia("(pointer: coarse)");
  query.addEventListener("change", notify);
  return () => query.removeEventListener("change", notify);
}

type ComboboxFieldProps = {
  label: string;
  name: string;
  options: SelectOption[];
  defaultValue?: string;
  /** Hint inside the search box while it is closed and nothing is picked (the empty option's label is used when there is one). */
  placeholder?: string;
  /** Shown when the search matches nothing. */
  emptyText: string;
  required?: boolean;
};

/** A select with a search box for long lists (grouped industries, time zones). Keyboard: arrows,
 * Home/End, Enter, Escape. On touch devices the native select is kept: there it is the better control. */
export function ComboboxField(props: ComboboxFieldProps) {
  const coarse = useSyncExternalStore(
    subscribeCoarse,
    () => window.matchMedia("(pointer: coarse)").matches,
    () => false,
  );
  if (coarse) {
    return <SelectField label={props.label} name={props.name} options={props.options} defaultValue={props.defaultValue} required={props.required} />;
  }
  return <DesktopCombobox {...props} />;
}

function DesktopCombobox({ label, name, options, defaultValue = "", placeholder, emptyText, required }: ComboboxFieldProps) {
  const id = useId();
  const listId = `${id}-list`;
  const root = useRef<HTMLDivElement>(null);
  const [value, setValue] = useState(defaultValue);
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [active, setActive] = useState(0);

  const selected = options.find((option) => option.value === value);
  // The option with an empty value only says "nothing chosen": it is the placeholder, not a row to search.
  const emptyOption = options.find((option) => option.value === "");
  const choices = useMemo(() => {
    const needle = query.trim().toLowerCase();
    return options.filter(
      (option) => option.value !== "" && (!needle || `${option.label} ${option.group ?? ""}`.toLowerCase().includes(needle)),
    );
  }, [options, query]);
  const rows = emptyOption && !query.trim() ? [emptyOption, ...choices] : choices;

  useEffect(() => {
    if (open) document.getElementById(`${id}-${active}`)?.scrollIntoView({ block: "nearest" });
  }, [open, active, id]);

  function openList() {
    if (open) return;
    setOpen(true);
    setActive(Math.max(0, rows.findIndex((row) => row.value === value)));
  }
  function close() {
    setOpen(false);
    setQuery("");
  }
  function pick(option: SelectOption) {
    setValue(option.value);
    close();
  }

  function onKeyDown(event: React.KeyboardEvent<HTMLInputElement>) {
    switch (event.key) {
      case "ArrowDown":
      case "ArrowUp": {
        event.preventDefault();
        if (!open) return openList();
        const step = event.key === "ArrowDown" ? 1 : -1;
        setActive((current) => (rows.length ? (current + step + rows.length) % rows.length : 0));
        break;
      }
      case "Home":
      case "End":
        if (open) {
          event.preventDefault();
          setActive(event.key === "Home" ? 0 : rows.length - 1);
        }
        break;
      case "Enter":
        // Never submits the surrounding form from the list.
        if (open) {
          event.preventDefault();
          const row = rows[active];
          if (row) pick(row);
        }
        break;
      case "Escape":
        if (open) {
          event.preventDefault();
          event.stopPropagation();
          close();
        }
        break;
    }
  }

  return (
    <div
      ref={root}
      className="relative flex flex-col gap-1.5"
      onBlur={(event) => {
        if (!root.current?.contains(event.relatedTarget as Node | null)) close();
      }}
    >
      <label htmlFor={id} className="text-sm font-medium">
        {label}
      </label>
      <input type="hidden" name={name} value={value} />
      <div className="relative">
        <input
          id={id}
          role="combobox"
          aria-expanded={open}
          aria-controls={listId}
          aria-autocomplete="list"
          aria-activedescendant={open && rows[active] ? `${id}-${active}` : undefined}
          aria-required={required || undefined}
          autoComplete="off"
          className={`${CONTROL} pe-9`}
          dir="auto"
          placeholder={open ? (selected?.value ? selected.label : (placeholder ?? "")) : (placeholder ?? emptyOption?.label)}
          value={open ? query : (selected?.value ? selected.label : "")}
          onChange={(event) => {
            setQuery(event.target.value);
            setActive(0);
            setOpen(true);
          }}
          onClick={openList}
          onKeyDown={onKeyDown}
        />
        <ChevronDown aria-hidden="true" className="pointer-events-none absolute end-3 top-1/2 size-4 -translate-y-1/2 text-muted" />
      </div>
      {open && (
        <ul
          id={listId}
          role="listbox"
          aria-label={label}
          className="absolute inset-x-0 top-full z-20 mt-1 max-h-80 overflow-y-auto rounded-lg border border-border bg-surface p-1 shadow-lg"
        >
          {rows.length === 0 && (
            <li role="presentation" className="px-3 py-2 text-sm text-muted">
              {emptyText}
            </li>
          )}
          {rows.map((option, index) => {
            const header = option.value !== "" && option.group && option.group !== rows[index - 1]?.group ? option.group : undefined;
            return (
              <li key={`${option.group ?? ""}:${option.value}`} role="presentation">
                {header && (
                  <div role="presentation" className="px-3 pb-1 pt-2 text-xs font-semibold text-muted">
                    {header}
                  </div>
                )}
                <div
                  id={`${id}-${index}`}
                  role="option"
                  aria-selected={option.value === value}
                  className={`cursor-pointer rounded-md px-3 py-1.5 text-sm ${index === active ? "bg-primary/10" : ""} ${option.value === "" ? "text-muted" : ""}`}
                  // Keeps the focus in the search box so the list does not close before the click lands.
                  onMouseDown={(event) => event.preventDefault()}
                  onMouseMove={() => setActive(index)}
                  onClick={() => pick(option)}
                >
                  {option.label}
                </div>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
