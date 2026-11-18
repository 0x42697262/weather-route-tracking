import { config } from "@/config";
import type { MapStyleKey } from "@/features/preferences/preferences";
import { preferencesText } from "@/text";

export type MapStyleOption = Readonly<{
  url: string;
  label: string;
}>;

export const MAP_STYLES: Readonly<Record<MapStyleKey, MapStyleOption>> = {
  configured: { url: config.mapStyleUrl, label: preferencesText.mapStyles.configured },
};
