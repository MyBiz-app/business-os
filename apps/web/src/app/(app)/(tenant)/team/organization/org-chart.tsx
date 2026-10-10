"use client";

import { ChevronDown, Mail, MapPin, Phone, X } from "lucide-react";
import { useTranslations } from "next-intl";
import { useActionState, useEffect, useMemo, useRef, useState } from "react";

import { Avatar } from "@/components/avatar";
import { Field, SelectField } from "@/components/form/field";
import { FormError, FormNotice } from "@/components/form/form-message";
import { SubmitButton } from "@/components/form/submit-button";

import { saveOrganization, type TeamState } from "../actions";

export type OrgPerson = {
  id: string;
  name: string;
  email: string;
  phone: string | null;
  title: string | null;
  role: string;
  isOwner: boolean;
  reportsTo: string | null;
  avatar: string | null;
  branches: string[];
};

/** The reporting tree, top down: owners first, then whoever reports to no one. Each card opens
 * the person's details; a branch of the tree folds away. */
export function OrgChart({ people, canEdit }: { people: OrgPerson[]; canEdit: boolean }) {
  const t = useTranslations("organization");
  const [selected, setSelected] = useState<string | null>(null);
  const [folded, setFolded] = useState<Set<string>>(new Set());
  const { roots, children } = useMemo(() => {
    const known = new Set(people.map((p) => p.id));
    const children = new Map<string, OrgPerson[]>();
    const roots: OrgPerson[] = [];
    for (const person of people) {
      if (person.reportsTo && known.has(person.reportsTo)) {
        children.set(person.reportsTo, [...(children.get(person.reportsTo) ?? []), person]);
      } else roots.push(person);
    }
    roots.sort((a, b) => Number(b.isOwner) - Number(a.isOwner));
    return { roots, children };
  }, [people]);
  const person = people.find((p) => p.id === selected) ?? null;

  const toggle = (id: string) =>
    setFolded((current) => {
      const next = new Set(current);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });

  // A wide tree opens centered on its top.
  const scroller = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const element = scroller.current;
    if (element) element.scrollLeft = ((element.scrollWidth - element.clientWidth) / 2) * (getComputedStyle(element).direction === "rtl" ? -1 : 1);
  }, []);

  // People with no one under them, side by side under one manager, stack in a column instead:
  // the chart stays as wide as its managers, not as its whole team.
  const renderLeaf = (node: OrgPerson, index: number) => (
    <li key={node.id} className="org-leaf">
      {index > 0 && <span aria-hidden="true" className="block h-2 w-px bg-foreground/20" />}
      <button
        type="button"
        onClick={() => setSelected(node.id === selected ? null : node.id)}
        aria-pressed={node.id === selected}
        className={`flex w-48 items-center gap-2.5 rounded-xl border bg-surface px-2.5 py-2 text-start shadow-[var(--elevation)] transition-[border-color,box-shadow] duration-200 hover:shadow-[var(--elevation-hover)] ${
          node.id === selected ? "border-primary ring-2 ring-primary/25" : "border-border"
        }`}
      >
        <Avatar id={node.id} name={node.name} src={node.avatar} size="sm" />
        <span className="flex min-w-0 flex-col">
          <span dir="auto" className="truncate text-sm font-semibold">
            {node.name}
          </span>
          <span dir="auto" className="truncate text-xs text-muted">
            {node.title ?? node.role}
          </span>
        </span>
      </button>
    </li>
  );

  const renderNode = (node: OrgPerson) => {
    const reports = children.get(node.id) ?? [];
    const open = !folded.has(node.id);
    const stack = reports.length > 1 && reports.every((r) => !children.has(r.id));
    return (
      <li key={node.id}>
        <div className="flex flex-col items-center">
          <button
            type="button"
            onClick={() => setSelected(node.id === selected ? null : node.id)}
            aria-pressed={node.id === selected}
            className={`flex w-48 flex-col items-center gap-2 rounded-2xl border bg-surface px-3 pb-3 pt-4 text-center shadow-[var(--elevation)] transition-[border-color,box-shadow] duration-200 hover:shadow-[var(--elevation-hover)] ${
              node.id === selected ? "border-primary ring-2 ring-primary/25" : "border-border"
            }`}
          >
            <Avatar id={node.id} name={node.name} src={node.avatar} size="lg" />
            <span className="flex w-full flex-col">
              <span dir="auto" className="truncate text-sm font-semibold">
                {node.name}
              </span>
              <span dir="auto" className="truncate text-xs text-muted">
                {node.title ?? node.role}
              </span>
            </span>
            {node.branches.length > 0 && (
              <span className="flex max-w-full items-center gap-1 truncate rounded-full bg-primary/8 px-2 py-0.5 text-[0.6875rem] font-medium text-primary">
                <MapPin aria-hidden="true" className="size-3 shrink-0" />
                <span className="truncate">{node.branches.join(", ")}</span>
              </span>
            )}
          </button>
          {reports.length > 0 && (
            <button
              type="button"
              onClick={() => toggle(node.id)}
              aria-expanded={open}
              aria-label={open ? t("fold", { name: node.name }) : t("unfold", { name: node.name })}
              className="relative z-10 -mt-3 flex items-center gap-1 rounded-full border border-border bg-surface px-2 py-0.5 text-xs font-medium text-muted shadow-sm hover:text-foreground"
            >
              {reports.length}
              <ChevronDown
                aria-hidden="true"
                className={`size-3 transition-transform motion-reduce:transition-none ${open ? "" : "-rotate-90 rtl:rotate-90"}`}
              />
            </button>
          )}
        </div>
        {reports.length > 0 && open && (stack ? <ul className="org-stack">{reports.map(renderLeaf)}</ul> : <ul>{reports.map(renderNode)}</ul>)}
      </li>
    );
  };

  return (
    <div className="flex flex-col gap-6 lg:flex-row lg:items-start">
      <div ref={scroller} className="card min-w-0 flex-1 overflow-x-auto p-6">
        <ul className="org-tree mx-auto w-max">{roots.map(renderNode)}</ul>
        {people.length === 1 && <p className="mt-6 text-center text-sm text-muted">{t("alone")}</p>}
      </div>
      {person && (
        <aside aria-label={person.name} className="card flex flex-col gap-4 p-5 lg:sticky lg:top-20 lg:w-80 lg:shrink-0">
          <div className="flex items-start gap-3">
            <Avatar id={person.id} name={person.name} src={person.avatar} size="lg" />
            <div className="flex min-w-0 flex-1 flex-col">
              <span dir="auto" className="truncate font-semibold">
                {person.name}
              </span>
              <span dir="auto" className="text-sm text-muted">
                {person.title ? `${person.title} · ${person.role}` : person.role}
              </span>
            </div>
            <button type="button" onClick={() => setSelected(null)} className="btn-ghost size-8 shrink-0" aria-label={t("close")}>
              <X aria-hidden="true" className="size-4" />
            </button>
          </div>
          <ul className="flex flex-col gap-2 text-sm">
            <li className="flex items-center gap-2">
              <Mail aria-hidden="true" className="size-4 text-muted" />
              <a href={`mailto:${person.email}`} dir="ltr" className="truncate underline-offset-4 hover:underline">
                {person.email}
              </a>
            </li>
            {person.phone && (
              <li className="flex items-center gap-2">
                <Phone aria-hidden="true" className="size-4 text-muted" />
                <a href={`tel:${person.phone}`} dir="ltr" className="underline-offset-4 hover:underline">
                  {person.phone}
                </a>
              </li>
            )}
            <li className="flex items-center gap-2">
              <MapPin aria-hidden="true" className="size-4 text-muted" />
              <span dir="auto">{person.branches.length > 0 ? person.branches.join(", ") : t("allBranches")}</span>
            </li>
          </ul>
          {canEdit && <OrganizationForm key={person.id} person={person} people={people} />}
        </aside>
      )}
    </div>
  );
}

/** Everyone below a person (they can't become that person's manager). */
function below(people: OrgPerson[], id: string): Set<string> {
  const result = new Set<string>();
  const queue = [id];
  while (queue.length) {
    const current = queue.pop()!;
    for (const p of people) {
      if (p.reportsTo === current && !result.has(p.id)) {
        result.add(p.id);
        queue.push(p.id);
      }
    }
  }
  return result;
}

function OrganizationForm({ person, people }: { person: OrgPerson; people: OrgPerson[] }) {
  const t = useTranslations();
  const [state, action] = useActionState<TeamState, FormData>(saveOrganization.bind(null, person.id), {});
  const excluded = below(people, person.id);
  const options = [
    { value: "", label: t("organization.nobody") },
    ...people
      .filter((p) => p.id !== person.id && !excluded.has(p.id))
      .map((p) => ({
        value: p.id,
        label: p.title ? `${p.name} · ${p.title}` : p.name,
      })),
  ];
  return (
    <form action={action} className="flex flex-col gap-3 border-t border-border pt-4">
      <FormError message={state.error && (state.error === "reporting_cycle" ? t("organization.cycle") : t("common.errors.generic"))} />
      <FormNotice message={state.created ? t("common.saved") : undefined} />
      <Field
        label={t("organization.jobTitle")}
        name="job_title"
        defaultValue={person.title ?? ""}
        maxLength={80}
        dir="auto"
        placeholder={t("organization.jobTitlePlaceholder")}
      />
      <SelectField label={t("organization.reportsTo")} name="reports_to" defaultValue={person.reportsTo ?? ""} options={options} />
      <p className="text-xs text-muted">{t("organization.accessNote")}</p>
      <div>
        <SubmitButton className="px-3 py-2 text-sm">{t("common.save")}</SubmitButton>
      </div>
    </form>
  );
}
