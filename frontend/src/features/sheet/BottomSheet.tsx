import type { ReactNode } from "react";
import { Drawer, DrawerContent, DrawerTitle } from "@/components/ui/drawer";
import {
  LOWEST_SHEET_HEIGHT,
  ORDERED_SNAP_POINTS,
  SHEET_HEIGHT_INFO,
  heightForSnapPoint,
  nextSheetHeight,
} from "@/features/sheet/sheetHeights";
import { useUiActions, useUiState } from "@/state/context";
import { sheetText } from "@/text";

type BottomSheetProps = Readonly<{
  title: string;
  headerAction: ReactNode;
  summary: ReactNode;
  aboveSheet: ReactNode;
  children: ReactNode;
}>;

export function BottomSheet({ title, headerAction, summary, aboveSheet, children }: BottomSheetProps) {
  const sheetHeight = useUiState((state) => state.sheetHeight);
  const { setSheetHeight } = useUiActions();
  const heightInfo = SHEET_HEIGHT_INFO[sheetHeight];

  const outside = (
    <>
      {heightInfo.showsMapControls ? (
        <div className="pointer-events-none absolute inset-x-0 bottom-full px-2 pb-2">{aboveSheet}</div>
      ) : null}
      <button
        type="button"
        aria-label={sheetText.changeHeight}
        className="flex h-11 w-full shrink-0 cursor-grab items-center justify-center"
        onClick={() => setSheetHeight(nextSheetHeight(sheetHeight))}
      >
        <span aria-hidden="true" className="h-1.5 w-12 rounded-full bg-muted-foreground/40" />
      </button>
    </>
  );

  return (
    <Drawer
      open
      modal={false}
      disablePointerDismissal
      snapPoints={ORDERED_SNAP_POINTS}
      snapPoint={heightInfo.snapPoint}
      onSnapPointChange={(snapPoint) => {
        const height = heightForSnapPoint(snapPoint);
        if (height !== null) {
          setSheetHeight(height);
        }
      }}
      onOpenChange={(open) => {
        if (!open) {
          setSheetHeight(LOWEST_SHEET_HEIGHT);
        }
      }}
    >
      <DrawerContent
        outside={outside}
        aria-label={sheetText.panelLabel}
        className="bg-background shadow-[0_-4px_16px_rgb(0_0_0/0.12)]"
      >
        <DrawerTitle className="sr-only">{title}</DrawerTitle>
        <div className="flex min-h-11 shrink-0 items-center justify-between gap-2 border-b px-4 pb-2">
          <div className="min-w-0 flex-1">{summary}</div>
          {headerAction}
        </div>
        <div className="min-h-0 flex-1 overflow-y-auto overscroll-contain px-4 pt-2 pb-[calc(var(--drawer-snap-point-offset,0px)+1rem)]">
          {children}
        </div>
      </DrawerContent>
    </Drawer>
  );
}
