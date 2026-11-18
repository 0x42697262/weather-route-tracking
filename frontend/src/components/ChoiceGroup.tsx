import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
import { cn } from "@/lib/utils";

export type Choice<Value extends string> = Readonly<{
  value: Value;
  label: string;
}>;

type ChoiceGroupProps<Value extends string> = Readonly<{
  label: string;
  choices: readonly Choice<Value>[];
  value: Value | null;
  onChange: (value: Value) => void;
  disabled?: boolean;
  orientation?: "horizontal" | "vertical";
  className?: string;
}>;

export function ChoiceGroup<Value extends string>({
  label,
  choices,
  value,
  onChange,
  disabled = false,
  orientation = "horizontal",
  className,
}: ChoiceGroupProps<Value>) {
  const handleChange = (pressed: readonly unknown[]) => {
    const next = choices.find((choice) => pressed.includes(choice.value));
    if (next !== undefined) {
      onChange(next.value);
    }
  };

  return (
    <ToggleGroup
      aria-label={label}
      variant="outline"
      spacing={0}
      value={value === null ? [] : [value]}
      onValueChange={handleChange}
      disabled={disabled}
      orientation={orientation}
      className={cn("w-full", className)}
    >
      {choices.map((choice) => (
        <ToggleGroupItem key={choice.value} value={choice.value} className="min-h-11 flex-1 px-3 aria-pressed:bg-primary aria-pressed:text-primary-foreground aria-pressed:hover:bg-primary/90 aria-pressed:hover:text-primary-foreground">
          {choice.label}
        </ToggleGroupItem>
      ))}
    </ToggleGroup>
  );
}
