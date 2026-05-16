import { describe, expect, it } from "vitest";

import { getOverallScanPercent, getScanProgressModel, normalizeScanStage } from "./scanProgress";

describe("scanProgress", () => {
  it("normalizes legacy stage aliases to the current scan stages", () => {
    expect(normalizeScanStage("scanning")).toBe("scan");
    expect(normalizeScanStage("clustering")).toBe("compare");
    expect(normalizeScanStage("scoring")).toBe("compare");
  });

  it("maps the active backend sub-stage to a single overall progress value", () => {
    expect(getOverallScanPercent({ stage: "scan", current: 2, total: 4, percent: 50 })).toBe(28);
    expect(getOverallScanPercent({ stage: "matching", current: 1, total: 2, percent: 50 })).toBe(58);
    expect(getOverallScanPercent({ stage: "quality", current: 1, total: 2, percent: 50 })).toBe(77);
    expect(getOverallScanPercent({ stage: "compare", current: 4, total: 10, percent: 40 })).toBe(90);
    expect(getOverallScanPercent({ stage: "complete", current: 1, total: 1, percent: 100 })).toBe(100);
  });

  it("returns the visual model used by the scanning UI", () => {
    expect(getScanProgressModel({ stage: "quality", current: 1, total: 2, percent: 50 })).toMatchObject({
      stageKey: "quality",
      stageLabel: "מחשב איכות",
      stagePercent: 50,
      overallPercent: 77,
      isComplete: false,
    });
  });
});
