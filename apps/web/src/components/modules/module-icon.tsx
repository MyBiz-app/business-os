import {
  BarChart3,
  Bot,
  Building2,
  Crown,
  Headphones,
  Luggage,
  Megaphone,
  MessageCircle,
  MessagesSquare,
  Rocket,
  Smartphone,
  Sparkles,
  Store,
  Target,
  Wallet,
  WandSparkles,
  Workflow,
} from "lucide-react";

/** Each module's icon and color, shared by the pricing page, the sign-up journey and its cart. */
const MODULES = {
  client_app: { icon: Smartphone, gradient: "from-sky-500 to-indigo-500" },
  client_app_branded: { icon: Store, gradient: "from-indigo-500 to-violet-600" },
  ai_basic: { icon: Bot, gradient: "from-violet-500 to-fuchsia-500" },
  ai_pro: { icon: Sparkles, gradient: "from-fuchsia-500 to-pink-500" },
  crm: { icon: Target, gradient: "from-amber-500 to-orange-500" },
  whatsapp: { icon: MessageCircle, gradient: "from-emerald-500 to-teal-500" },
  whatsapp_ai: { icon: MessagesSquare, gradient: "from-teal-500 to-cyan-600" },
  crm_automation: { icon: Workflow, gradient: "from-orange-500 to-red-500" },
  pack_plus: { icon: Luggage, gradient: "from-sky-500 to-cyan-500" },
  pack_max: { icon: Luggage, gradient: "from-blue-600 to-indigo-600" },
  support_priority: { icon: Headphones, gradient: "from-pink-500 to-rose-500" },
  support_vip: { icon: Crown, gradient: "from-amber-400 to-yellow-600" },
  setup_guided: { icon: WandSparkles, gradient: "from-violet-500 to-purple-600" },
  setup_full: { icon: Rocket, gradient: "from-fuchsia-500 to-violet-600" },
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
