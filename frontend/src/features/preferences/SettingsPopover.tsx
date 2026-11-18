import { Settings } from "lucide-react";
import { ChoiceGroup } from "@/components/ChoiceGroup";
import { Button } from "@/components/ui/button";
import { Popover, PopoverContent, PopoverTitle, PopoverTrigger } from "@/components/ui/popover";
import { usePreferences, useUpdatePreferences } from "@/features/preferences/context";
import { MAP_STYLES } from "@/features/preferences/mapStyles";
import { MAP_STYLE_KEYS } from "@/features/preferences/preferences";
import { UNIT_SYSTEMS } from "@/lib/units";
import { preferencesText } from "@/text";

const UNIT_CHOICES = UNIT_SYSTEMS.map((system) => ({
  value: system,
  label: preferencesText.units[system],
}));

const MAP_STYLE_CHOICES = MAP_STYLE_KEYS.map((key) => ({ value: key, label: MAP_STYLES[key].label }));

export function SettingsPopover() {
  const preferences = usePreferences();
  const updatePreferences = useUpdatePreferences();

  return (
    <Popover>
      <PopoverTrigger
        render={
          <Button
            variant="ghost"
            size="icon"
            className="size-11"
            aria-label={preferencesText.openSettings}
          />
        }
      >
        <Settings className="size-5" />
      </PopoverTrigger>
      <PopoverContent align="end" className="w-80">
        <PopoverTitle className="text-base font-medium">{preferencesText.title}</PopoverTitle>
        <div className="flex flex-col gap-1.5">
          <span aria-hidden="true" className="text-sm text-muted-foreground">
            {preferencesText.unitsLabel}
          </span>
          <ChoiceGroup
            label={preferencesText.unitsLabel}
            choices={UNIT_CHOICES}
            value={preferences.units}
            onChange={(units) => updatePreferences({ units })}
            orientation="vertical"
          />
        </div>
        <div className="flex flex-col gap-1.5">
          <span aria-hidden="true" className="text-sm text-muted-foreground">
            {preferencesText.mapStyleLabel}
          </span>
          <ChoiceGroup
            label={preferencesText.mapStyleLabel}
            choices={MAP_STYLE_CHOICES}
            value={preferences.mapStyle}
            onChange={(mapStyle) => updatePreferences({ mapStyle })}
          />
        </div>
      </PopoverContent>
    </Popover>
  );
}
