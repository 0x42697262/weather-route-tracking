export const HEATMAP_STATUSES = ["idle", "loading", "failed", "ready"] as const;

export type HeatmapStatus = (typeof HEATMAP_STATUSES)[number];
