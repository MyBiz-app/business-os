"use client";

import { useTranslations } from "next-intl";
import { useEffect, useId, useRef, useState } from "react";

/** What a saved address looks like when it is loaded back into the form. */
export type AddressDefaults = {
  city_code?: number | null;
  city_name?: string | null;
  street_code?: number | null;
  street_name?: string | null;
  house_number?: string | null;
  address_details?: string | null;
  street_unlisted?: string | null;
};

type Option = { code: number; label: string; hint?: string };

/** Looks names up on the server (the official lists) as the person types. */
function useOptions(url: string | null, query: string, open: boolean): Option[] | null {
  const [found, setFound] = useState<Option[] | null>(null);
  useEffect(() => {
    if (!url || !open) return;
    const controller = new AbortController();
    const timer = setTimeout(async () => {
      try {
        const response = await fetch(`${url}?q=${encodeURIComponent(query)}&limit=12`, { signal: controller.signal });
        if (!response.ok) return setFound([]);
        const rows = (await response.json()) as { code: number; name_he: string; name_en?: string | null; aliases?: string[] }[];
        setFound(rows.map((row) => ({ code: row.code, label: row.name_he, hint: row.name_en ?? undefined })));
      } catch {
        /* aborted by the next keystroke */
      }
    }, 150);
    return () => {
      clearTimeout(timer);
      controller.abort();
    };
  }, [url, query, open]);
  return url && open ? found : null;
}

type ComboboxProps = {
  label: string;
  placeholder: string;
  text: string;
  chosen: boolean;
  url: string | null;
  disabled?: boolean;
  required?: boolean;
  invalidMessage: string;
  disabledHint?: string;
  onText: (text: string) => void;
  onPick: (option: Option) => void;
};

/** A text box that suggests official names; only a name picked from the list counts. */
function Combobox({ label, placeholder, text, chosen, url, disabled, required, invalidMessage, disabledHint, onText, onPick }: ComboboxProps) {
  const t = useTranslations("address");
  const id = useId();
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(0);
  const input = useRef<HTMLInputElement>(null);
  const options = useOptions(url, text, open && !chosen);
  const showList = open && !chosen && !disabled && options !== null;

  useEffect(() => {
    input.current?.setCustomValidity(required && !chosen && !disabled ? invalidMessage : "");
  }, [required, chosen, disabled, invalidMessage]);

  function pick(option: Option) {
    onPick(option);
    setOpen(false);
  }

  return (
    <div className="relative flex flex-col gap-1.5">
      <label htmlFor={id} className="text-sm font-medium">
        {label}
      </label>
      <input
        ref={input}
        id={id}
        role="combobox"
        aria-expanded={showList}
        aria-controls={`${id}-list`}
        aria-autocomplete="list"
        aria-activedescendant={showList && options[active] ? `${id}-${options[active].code}` : undefined}
        autoComplete="off"
        dir="auto"
        className="control w-full min-w-0 px-3 py-2"
        placeholder={disabled ? disabledHint : placeholder}
        disabled={disabled}
        value={text}
        onChange={(event) => {
          onText(event.target.value);
          setOpen(true);
          setActive(0);
        }}
        onFocus={() => setOpen(true)}
        onBlur={() => setTimeout(() => setOpen(false), 120)}
        onKeyDown={(event) => {
          if (!showList) return;
          if (event.key === "ArrowDown") {
            event.preventDefault();
            setActive((active + 1) % Math.max(options.length, 1));
          } else if (event.key === "ArrowUp") {
            event.preventDefault();
            setActive((active - 1 + options.length) % Math.max(options.length, 1));
          } else if (event.key === "Enter" && options[active]) {
            event.preventDefault();
            pick(options[active]);
          } else if (event.key === "Escape") {
            setOpen(false);
          }
        }}
      />
      {showList && (
        <ul id={`${id}-list`} role="listbox" aria-label={label} className="popover absolute inset-x-0 top-full z-40 mt-1 max-h-60 overflow-auto p-1">
          {options.length === 0 && <li className="px-3 py-2 text-sm text-muted">{t("noResults")}</li>}
          {options.map((option, index) => (
            <li
              key={option.code}
              id={`${id}-${option.code}`}
              role="option"
              aria-selected={index === active}
              className="flex cursor-pointer items-baseline justify-between gap-3 rounded-lg px-3 py-2 text-sm aria-selected:bg-primary/10"
              onMouseDown={(event) => {
                event.preventDefault();
                pick(option);
              }}
              onMouseEnter={() => setActive(index)}
            >
              <span dir="auto">{option.label}</span>
              {option.hint && (
                <span dir="ltr" className="text-xs text-muted">
                  {option.hint}
                </span>
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

type Props = {
  defaults?: AddressDefaults;
  /** City, street and house number must all be filled in. */
  required?: boolean;
  /** Where the address lives in the form, for forms with more than one. */
  prefix?: string;
  disabled?: boolean;
  /** The older free-text address of something saved before the lists existed. */
  legacyText?: string | null;
};

/**
 * One address, the same everywhere: pick a city from the official list, then a street of that
 * city, then a house number and details. A street that is not on the list can be typed
 * ("my street is not listed"); it is flagged for review. Sends city_code, street_code,
 * street_unlisted, house_number and address_details with the form (see lib/address.ts).
 */
export function AddressPicker({ defaults = {}, required = false, prefix = "", disabled = false, legacyText = null }: Props) {
  const t = useTranslations("address");
  const [city, setCity] = useState({ code: defaults.city_code ?? null, text: defaults.city_name ?? "" });
  const [street, setStreet] = useState({ code: defaults.street_code ?? null, text: defaults.street_name ?? "" });
  const [unlisted, setUnlisted] = useState(Boolean(defaults.street_unlisted));
  const [unlistedText, setUnlistedText] = useState(defaults.street_unlisted ?? "");
  const name = (field: string) => `${prefix}${field}`;

  return (
    <div className="grid gap-4 sm:grid-cols-2">
      {legacyText && !defaults.city_code && (
        <p dir="auto" className="text-sm text-muted sm:col-span-2">
          {t("current", { address: legacyText })}
        </p>
      )}
      <Combobox
        label={t("city")}
        placeholder={t("cityPlaceholder")}
        text={city.text}
        chosen={city.code !== null}
        url="/geo/cities"
        disabled={disabled}
        required={required}
        invalidMessage={t("chooseCity")}
        onText={(text) => {
          setCity({ code: null, text });
          setStreet({ code: null, text: "" });
        }}
        onPick={(option) => {
          setCity({ code: option.code, text: option.label });
          setStreet({ code: null, text: "" });
        }}
      />
      {unlisted ? (
        <div className="flex flex-col gap-1.5">
          <label htmlFor={`${name("street_unlisted")}-input`} className="text-sm font-medium">
            {t("unlistedStreet")}
          </label>
          <input
            id={`${name("street_unlisted")}-input`}
            className="control w-full min-w-0 px-3 py-2"
            dir="auto"
            maxLength={120}
            required={required}
            disabled={disabled}
            value={unlistedText}
            onChange={(event) => setUnlistedText(event.target.value)}
          />
          <p className="text-xs text-muted">{t("unlistedNote")}</p>
          <button type="button" className="btn-link self-start text-xs" onClick={() => setUnlisted(false)}>
            {t("backToList")}
          </button>
        </div>
      ) : (
        <div className="flex flex-col gap-1.5">
          <Combobox
            label={t("street")}
            placeholder={t("streetPlaceholder")}
            disabledHint={t("streetNeedsCity")}
            text={street.text}
            chosen={street.code !== null}
            url={city.code === null ? null : `/geo/cities/${city.code}/streets`}
            disabled={disabled || city.code === null}
            required={required}
            invalidMessage={t("chooseStreet")}
            onText={(text) => setStreet({ code: null, text })}
            onPick={(option) => setStreet({ code: option.code, text: option.label })}
          />
          {city.code !== null && !disabled && (
            <button type="button" className="btn-link self-start text-xs" onClick={() => setUnlisted(true)}>
              {t("unlisted")}
            </button>
          )}
        </div>
      )}
      <div className="flex flex-col gap-1.5">
        <label htmlFor={`${name("house_number")}-input`} className="text-sm font-medium">
          {t("houseNumber")}
        </label>
        <input
          id={`${name("house_number")}-input`}
          name={name("house_number")}
          className="control w-full min-w-0 px-3 py-2"
          dir="auto"
          maxLength={20}
          required={required}
          disabled={disabled}
          defaultValue={defaults.house_number ?? ""}
          autoComplete="off"
        />
      </div>
      <div className="flex flex-col gap-1.5">
        <label htmlFor={`${name("address_details")}-input`} className="text-sm font-medium">
          {t("details")} <span className="text-xs font-normal text-muted">({t("optional")})</span>
        </label>
        <input
          id={`${name("address_details")}-input`}
          name={name("address_details")}
          className="control w-full min-w-0 px-3 py-2"
          dir="auto"
          maxLength={100}
          disabled={disabled}
          defaultValue={defaults.address_details ?? ""}
          autoComplete="off"
        />
      </div>
      {defaults.city_code && city.code === null && <input type="hidden" name={name("address_clear")} value="1" />}
      <input type="hidden" name={name("city_code")} value={city.code ?? ""} disabled={disabled} />
      <input type="hidden" name={name("street_code")} value={unlisted ? "" : (street.code ?? "")} disabled={disabled} />
      <input type="hidden" name={name("street_unlisted")} value={unlisted ? unlistedText : ""} disabled={disabled} />
    </div>
  );
}
