import type { ReactNode } from "react";
import { WIDE_LANDSCAPE_MEDIA_QUERY } from "@/constants";
import { useMediaQuery } from "@/hooks/useMediaQuery";
import { BottomSheet } from "@/features/sheet/BottomSheet";
import { SidePanel } from "@/features/sheet/SidePanel";

type AppLayoutProps = Readonly<{
  map: ReactNode;
  mapControls: ReactNode;
  title: string;
  headerAction: ReactNode;
  summary: ReactNode;
  panel: ReactNode;
}>;

export function AppLayout({ map, mapControls, title, headerAction, summary, panel }: AppLayoutProps) {
  const wide = useMediaQuery(WIDE_LANDSCAPE_MEDIA_QUERY);

  if (wide) {
    return (
      <div className="flex h-dvh w-full">
        <SidePanel title={title} headerAction={headerAction} summary={summary}>
          {panel}
        </SidePanel>
        <div className="relative min-w-0 flex-1">
          {map}
          <div className="pointer-events-none absolute bottom-4 left-4 w-[min(28rem,calc(100%-2rem))]">
            {mapControls}
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="relative h-dvh w-full">
      {map}
      <BottomSheet title={title} headerAction={headerAction} summary={summary} aboveSheet={mapControls}>
        {panel}
      </BottomSheet>
    </div>
  );
}
