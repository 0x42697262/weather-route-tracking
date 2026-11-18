import type { ReactNode } from "react";
import { sheetText } from "@/text";

type SidePanelProps = Readonly<{
  title: string;
  headerAction: ReactNode;
  summary: ReactNode;
  children: ReactNode;
}>;

export function SidePanel({ title, headerAction, summary, children }: SidePanelProps) {
  return (
    <aside
      aria-label={sheetText.panelLabel}
      className="flex h-full w-96 shrink-0 flex-col border-r bg-background"
    >
      <h2 className="sr-only">{title}</h2>
      <div className="flex min-h-14 shrink-0 items-center justify-between gap-2 border-b px-4 py-2">
        <div className="min-w-0 flex-1">{summary}</div>
        {headerAction}
      </div>
      <div className="min-h-0 flex-1 overflow-y-auto px-4 pt-2 pb-4">{children}</div>
    </aside>
  );
}
