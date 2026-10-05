import type { Icon } from "@business-os/verticals";
import { Briefcase, Camera, Car, Dumbbell, GraduationCap, PawPrint, Scissors, Stethoscope, Trophy, Wrench } from "lucide-react";

const ICONS: Record<Icon, typeof Dumbbell> = {
  dumbbell: Dumbbell,
  scissors: Scissors,
  stethoscope: Stethoscope,
  "graduation-cap": GraduationCap,
  car: Car,
  trophy: Trophy,
  wrench: Wrench,
  "paw-print": PawPrint,
  camera: Camera,
  briefcase: Briefcase,
};

/** An industry's icon from the catalog (decorative: the industry's name is always next to it). */
export function VerticalIcon({ icon, className }: { icon: Icon; className?: string }) {
  const Component = ICONS[icon];
  return <Component aria-hidden="true" className={className} />;
}
