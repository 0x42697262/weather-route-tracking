import {
  Ban,
  CircleAlert,
  CircleHelp,
  OctagonAlert,
  ShieldCheck,
  Ship,
  TriangleAlert,
  type LucideIcon,
} from "lucide-react";
import type { ColorKey } from "@/theme/colors";

export const LEVEL_ICONS: Readonly<Record<ColorKey, LucideIcon>> = {
  "risk-low": ShieldCheck,
  "risk-moderate": CircleAlert,
  "risk-high": TriangleAlert,
  "risk-severe": OctagonAlert,
  "risk-no-travel": Ban,
  "risk-unknown": CircleHelp,
  ferry: Ship,
};
