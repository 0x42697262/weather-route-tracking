import { SlidersHorizontal } from "lucide-react";
import { Button } from "@/components/ui/button";
import { formText } from "@/text";

type CustomOptionsNoticeProps = Readonly<{
  onReset: () => void;
}>;

export function CustomOptionsNotice({ onReset }: CustomOptionsNoticeProps) {
  return (
    <div className="flex items-center justify-between gap-2 rounded-lg bg-muted px-3 py-1 text-sm">
      <span className="flex items-center gap-2">
        <SlidersHorizontal aria-hidden="true" className="size-4" />
        {formText.customOptions}
      </span>
      <Button type="button" variant="link" className="min-h-11 px-0" onClick={onReset}>
        {formText.resetDefaults}
      </Button>
    </div>
  );
}
