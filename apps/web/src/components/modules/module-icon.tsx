import { BarChart3, Bot, Building2, Megaphone, MessageCircle, Smartphone, Sparkles, Target, Wallet } from "lucide-react";

/** Each module's icon and color, shared by the pricing page, the sign-up journey and its cart. */
const MODULES = {
  client_app: { icon: Smartphone, gradient: "from-sky-500 to-indigo-500" },
  ai_basic: { icon: Bot, gradient: "from-violet-500 to-fuchsia-500" },
  ai_pro: { icon: Sparkles, gradient: "from-fuchsia-500 to-pink-500" },
  crm: { icon: Target, gradient: "from-amber-500 to-orange-500" },
  whatsapp: { icon: MessageCircle, gradient: "from-emerald-500 to-teal-500" },
  analytics_pro: { icon: BarChart3, gradient: "from-cyan-500 to-blue-500" },
  agent_finance: { icon: Wallet, gradient: "from-lime-500 to-emerald-600" },
  agent_marketing: { icon: Megaphone, gradient: "from-rose-500 to-orange-500" },
  extra_location: { icon: Building2, gradient: "from-slate-500 to-slate-700" },
} as const;

type Key = keyof typeof MODULES;

/** A module's icon on a colored tile (decorative: the module's name is always next to it). */
export function ModuleIcon({ module, size = "md" }: { module: string; size?: "sm" | "md" | "lg" }) {
  const entry = MODULES[module as Key] ?? MODULES.ai_basic;
  const Icon = entry.icon;
  const box = { sm: "size-8 rounded-lg", md: "size-11 rounded-xl", lg: "size-14 rounded-2xl" }[size];
  const glyph = { sm: "size-4", md: "size-5", lg: "size-7" }[size];
  return (
    <span aria-hidden="true" className={`inline-flex shrink-0 items-center justify-center bg-gradient-to-br text-white shadow-sm ${entry.gradient} ${box}`}>
      <Icon className={glyph} />
    </span>
  );
}
