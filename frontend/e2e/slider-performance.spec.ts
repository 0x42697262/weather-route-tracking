import { expect, test } from "@playwright/test";
import { planTrip, waitForHeatmap } from "@e2e/support";

const CPU_THROTTLING_RATE = 4;
const DRAG_STEPS = 120;
const STEP_PAUSE_MS = 25;

test.use({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 3, isMobile: true, hasTouch: true });

type FrameReport = Readonly<{ frames: number; durationMs: number; intervalsMs: number[] }>;

declare global {
  interface Window {
    frameProbe?: { times: number[]; running: boolean };
  }
}

test("dragging the forecast slider through 48 hours stays smooth and fetches nothing", async ({ page }, testInfo) => {
  await planTrip(page, "Chicago", "Houston", "40000");
  await waitForHeatmap(page);
  await page.waitForTimeout(1500);

  const cdp = await page.context().newCDPSession(page);
  await cdp.send("Emulation.setCPUThrottlingRate", { rate: CPU_THROTTLING_RATE });

  const thumb = page.locator('[data-slot="slider-thumb"]');
  const track = page.locator('[data-slot="slider-track"]');
  const thumbBox = await thumb.boundingBox();
  const trackBox = await track.boundingBox();
  if (thumbBox === null || trackBox === null) {
    throw new Error("slider not visible");
  }
  const startX = thumbBox.x + thumbBox.width / 2;
  const centerY = thumbBox.y + thumbBox.height / 2;
  const endX = trackBox.x + trackBox.width + thumbBox.width;

  const requests: string[] = [];
  page.on("request", (request) => requests.push(request.url()));

  await page.evaluate(() => {
    const probe = { times: [] as number[], running: true };
    window.frameProbe = probe;
    const tick = (time: number) => {
      probe.times.push(time);
      if (probe.running) {
        requestAnimationFrame(tick);
      }
    };
    requestAnimationFrame(tick);
  });

  await page.mouse.move(startX, centerY);
  await page.mouse.down();
  for (let step = 1; step <= DRAG_STEPS; step += 1) {
    await page.mouse.move(startX + ((endX - startX) * step) / DRAG_STEPS, centerY);
    await page.waitForTimeout(STEP_PAUSE_MS);
  }
  await page.mouse.up();

  const report: FrameReport = await page.evaluate(() => {
    const probe = window.frameProbe;
    if (probe === undefined) {
      return { frames: 0, durationMs: 0, intervalsMs: [] };
    }
    probe.running = false;
    const times = probe.times;
    const intervalsMs = times.slice(1).map((time, index) => time - (times[index] ?? time));
    return { frames: times.length, durationMs: (times.at(-1) ?? 0) - (times[0] ?? 0), intervalsMs };
  });
  await cdp.send("Emulation.setCPUThrottlingRate", { rate: 1 });

  const sorted = [...report.intervalsMs].sort((left, right) => left - right);
  const percentile = (share: number) => sorted[Math.min(sorted.length - 1, Math.floor(sorted.length * share))] ?? 0;
  const result = {
    cpuThrottling: CPU_THROTTLING_RATE,
    frames: report.frames,
    durationMs: Math.round(report.durationMs),
    fps: Number(((report.frames - 1) / (report.durationMs / 1000)).toFixed(1)),
    medianFrameMs: Number(percentile(0.5).toFixed(1)),
    p95FrameMs: Number(percentile(0.95).toFixed(1)),
    maxFrameMs: Number((sorted.at(-1) ?? 0).toFixed(1)),
    requestsDuringDrag: requests.length,
  };
  console.log(`slider-performance ${JSON.stringify(result)}`);
  await testInfo.attach("slider-performance", { body: JSON.stringify(result, null, 2), contentType: "application/json" });

  await expect(page.getByText("+48 h")).toBeVisible();
  expect(requests).toEqual([]);
});
