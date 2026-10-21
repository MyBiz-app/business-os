"use client";

import { ImageUp, Trash2 } from "lucide-react";
import { useTranslations } from "next-intl";
import { useRef, useState } from "react";

import { ImageCropDialog } from "@/components/image-crop-dialog";

import { AgentAvatar } from "./agent-avatar";
import { avatarFor } from "./avatars";
import { COLORS, GALLERY, SYSTEM_ROLES, TOOL_DOMAINS } from "@/lib/agent-templates";
import type { Agent } from "./types";
import { Button } from "@/components/ui/button";

/** What a face picker holds: a gallery face, a picture to upload (already cropped), or the agent's current one. */
export type Face = { preset: string | null; file: File | null; preview: string | null };

export type RoleOption = { id: string; name: string };

/** The agent's face: pick from the gallery or upload a picture (cropped to a circle first). */
export function FaceChooser({ agent, face, onChange }: { agent: Pick<Agent, "key" | "name" | "color" | "avatar_preset" | "avatar_key" | "avatar_url">; face: Face; onChange: (face: Face) => void }) {
  const t = useTranslations("aiTeam.wizard");
  const [cropping, setCropping] = useState<File | null>(null);
  const input = useRef<HTMLInputElement>(null);
  const shown = face.preview ? { ...agent, avatar_url: null, avatar_preset: null } : { ...agent, avatar_preset: face.preset ?? agent.avatar_preset };
  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-wrap items-center gap-4">
        {face.preview ? (
          // eslint-disable-next-line @next/next/no-img-element -- a local preview of the cropped picture
          <img src={face.preview} alt="" className="size-20 rounded-full object-cover" />
        ) : (
          <AgentAvatar agent={shown} className="size-20" />
        )}
        <div className="flex flex-wrap gap-2">
          <label className="btn-secondary cursor-pointer px-3 py-2 text-sm has-[:focus-visible]:ring-2 has-[:focus-visible]:ring-primary">
            <ImageUp aria-hidden="true" className="size-4" />
            {t("upload")}
            <input ref={input} type="file" accept="image/png,image/jpeg,image/webp" className="sr-only" onChange={(e) => setCropping(e.target.files?.[0] ?? null)} />
          </label>
          {(face.preview || face.preset) && (
            <Button variant="quiet" type="button" onClick={() => onChange({ preset: null, file: null, preview: null })}>
              <Trash2 aria-hidden="true" className="size-4" />
              {t("resetFace")}
            </Button>
          )}
        </div>
      </div>
      <p className="text-xs text-muted">{t("uploadHint")}</p>
      <ul role="radiogroup" aria-label={t("gallery")} className="grid grid-cols-8 gap-2">
        {GALLERY.map((preset) => {
          const src = avatarFor(preset, preset);
          const checked = !face.preview && face.preset === preset;
          return (
            <li key={preset}>
              <Button variant="plain" type="button" role="radio" aria-checked={checked} aria-label={preset} onClick={() => onChange({ preset, file: null, preview: null })} className={`block w-full rounded-full p-0.5 focus-visible:ring-2 focus-visible:ring-primary ${checked ? "ring-2 ring-primary" : "opacity-80 hover:opacity-100"}`}>
                {/* eslint-disable-next-line @next/next/no-img-element -- small fingerprinted files from our own package */}
                {src && <img src={src} alt="" draggable={false} className="aspect-square w-full rounded-full object-cover" />}
              </Button>
            </li>
          );
        })}
      </ul>
      {cropping && (
        <ImageCropDialog
          file={cropping}
          onCancel={() => {
            setCropping(null);
            if (input.current) input.current.value = "";
          }}
          onDone={(file) => {
            setCropping(null);
            onChange({ preset: null, file, preview: URL.createObjectURL(file) });
          }}
        />
      )}
    </div>
  );
}

export function ColorChoice({ value, onChange }: { value: string; onChange: (color: string) => void }) {
  const t = useTranslations("aiTeam.wizard");
  return (
    <div role="radiogroup" aria-label={t("color")} className="flex flex-wrap items-center gap-2">
      {COLORS.map((color) => (
        <Button variant="plain" key={color} type="button" role="radio" aria-checked={value.toLowerCase() === color.toLowerCase()} aria-label={color} onClick={() => onChange(color)} className={`size-8 rounded-full border-2 focus-visible:ring-2 focus-visible:ring-primary ${value.toLowerCase() === color.toLowerCase() ? "border-foreground" : "border-transparent"}`} style={{ backgroundColor: color }} />
      ))}
    </div>
  );
}

function Checks({ legend, options, value, onChange }: { legend: string; options: { id: string; label: string }[]; value: string[]; onChange: (next: string[]) => void }) {
  const toggle = (id: string) => onChange(value.includes(id) ? value.filter((v) => v !== id) : [...value, id]);
  return (
    <fieldset className="flex flex-col gap-2">
      <legend className="text-sm font-medium">{legend}</legend>
      <div className="grid gap-1.5 sm:grid-cols-2">
        {options.map((option) => (
          <label key={option.id} className="flex cursor-pointer items-center gap-2 rounded-lg px-2 py-1.5 text-sm hover:bg-surface">
            <input type="checkbox" checked={value.includes(option.id)} onChange={() => toggle(option.id)} className="size-4 accent-[var(--primary)]" />
            <span dir="auto">{option.label}</span>
          </label>
        ))}
      </div>
    </fieldset>
  );
}

/** The agent's toolbox: which parts of the business it can look into (and, with the person's permission, act on). */
export function DomainChecks({ value, onChange }: { value: string[]; onChange: (next: string[]) => void }) {
  const t = useTranslations("aiTeam.wizard");
  return <Checks legend={t("domainsLegend")} options={TOOL_DOMAINS.map((id) => ({ id, label: t(`domains.${id}` as "domains.clients") }))} value={value} onChange={onChange} />;
}

/** Who may talk to the agent: the built-in roles and the business's own. */
export function RoleChecks({ value, custom, onChange }: { value: string[]; custom: RoleOption[]; onChange: (next: string[]) => void }) {
  const t = useTranslations("aiTeam.wizard");
  const tRoles = useTranslations("aiTeam.roles");
  const options = [...SYSTEM_ROLES.map((id) => ({ id, label: tRoles(id) })), ...custom.map((r) => ({ id: r.id, label: r.name }))];
  return <Checks legend={t("rolesLegend")} options={options} value={value} onChange={onChange} />;
}
