import type { Meta, StoryObj } from "@storybook/nextjs-vite";
import { NextIntlClientProvider } from "next-intl";

import en from "../../../../../packages/i18n/messages/en.json";
import he from "../../../../../packages/i18n/messages/he.json";
import { SettingsGroup } from "@/app/(app)/(tenant)/settings/settings-group";

import { InputRow, SelectRow, SettingsRows, SwitchRow } from "./rows";
import { SaveBar } from "./save-bar";

const meta: Meta = { title: "Components/Settings rows" };
export default meta;
type Story = StoryObj;

const MESSAGES = { en, he };

function Page({ locale }: { locale: "en" | "he" }) {
  const he = locale === "he";
  return (
    <NextIntlClientProvider locale={locale} messages={MESSAGES[locale]}>
      <form className="@container mx-auto flex max-w-3xl flex-col gap-8" onSubmit={(event) => event.preventDefault()}>
        <SettingsGroup id="details" title={he ? "פרטי העסק" : "Business details"} description={he ? "שם, שפה, מטבע ואזור זמן." : "Name, language, currency and time zone."}>
          <SettingsRows>
            <InputRow label={he ? "שם העסק" : "Business name"} name="name" defaultValue={he ? "אדיר פיטנס" : "Adir Fitness"} />
            <InputRow label={he ? "אתר" : "Website"} hint={he ? "הכתובת שתופיע בהודעות ללקוחות." : "Shown in messages to clients."} name="site" dir="ltr" defaultValue="www.example.com" />
            <SelectRow label={he ? "שפה" : "Language"} name="locale" defaultValue="a" options={[{ value: "a", label: he ? "עברית" : "Hebrew" }, { value: "b", label: "English" }]} />
          </SettingsRows>
        </SettingsGroup>
        <SettingsGroup id="clients" title={he ? "לקוחות" : "Clients"}>
          <SettingsRows>
            <SwitchRow label={he ? "נדרש מנוי להזמנה" : "Require a plan to book"} hint={he ? "לקוח בלי מנוי לא יוכל להזמין." : "Clients without a plan cannot book."} name="plan" defaultChecked />
            <SwitchRow label={he ? "הצהרת בריאות" : "Health declaration"} name="health" />
          </SettingsRows>
        </SettingsGroup>
        <SaveBar />
      </form>
    </NextIntlClientProvider>
  );
}

/** Change any field and the bar rises from the bottom; Discard puts everything back. */
export const English: Story = { render: () => <Page locale="en" /> };
export const Hebrew: Story = { render: () => <Page locale="he" />, globals: { direction: "rtl" } };
