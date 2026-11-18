import { setWorkerUrl } from "maplibre-gl";
import workerUrl from "maplibre-gl/dist/maplibre-gl-worker.mjs?url";

export function configureMapWorker(): void {
  setWorkerUrl(workerUrl);
}
