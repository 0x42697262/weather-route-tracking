import { SHEET_FULL_FRACTION, SHEET_HALF_FRACTION, SHEET_PEEK_HEIGHT_PX } from "@/constants";

export const SHEET_HEIGHTS = ["peek", "half", "full"] as const;

export type SheetHeight = (typeof SHEET_HEIGHTS)[number];

export type SnapPoint = number | string;

type SheetHeightInfo = Readonly<{
  snapPoint: SnapPoint;
  showsMapControls: boolean;
}>;

export const SHEET_HEIGHT_INFO: Readonly<Record<SheetHeight, SheetHeightInfo>> = {
  peek: { snapPoint: `${SHEET_PEEK_HEIGHT_PX}px`, showsMapControls: true },
  half: { snapPoint: SHEET_HALF_FRACTION, showsMapControls: true },
  full: { snapPoint: SHEET_FULL_FRACTION, showsMapControls: false },
};

export const LOWEST_SHEET_HEIGHT: SheetHeight = SHEET_HEIGHTS[0];

export const ORDERED_SNAP_POINTS: SnapPoint[] = SHEET_HEIGHTS.map(
  (height) => SHEET_HEIGHT_INFO[height].snapPoint,
);

export function heightForSnapPoint(snapPoint: SnapPoint | null): SheetHeight | null {
  return SHEET_HEIGHTS.find((height) => SHEET_HEIGHT_INFO[height].snapPoint === snapPoint) ?? null;
}

export function nextSheetHeight(height: SheetHeight): SheetHeight {
  const index = SHEET_HEIGHTS.indexOf(height);
  return SHEET_HEIGHTS[(index + 1) % SHEET_HEIGHTS.length] ?? LOWEST_SHEET_HEIGHT;
}
