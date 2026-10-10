import { createRequire } from "node:module";
import { describe, expect, it } from "vitest";

const require = createRequire(import.meta.url);
const builderConfig = require("./electron-builder.config.cjs");

describe("electron builder config", () => {
  it("packages the complete frozen backend directory", () => {
    expect(builderConfig.extraResources).toContainEqual({
      from: "../build/backend/album-deduplicator-api",
      to: "backend",
    });
  });
  it("does not ship a source backend that requires a user Python installation", () => {
    expect(builderConfig.extraResources.some(({ to }) => to.startsWith("backend-source"))).toBe(false);
  });
  it("serves the renderer from the frozen API resource root", () => {
    expect(builderConfig.extraResources).toContainEqual({
      from: "dist",
      to: "backend/_internal/frontend/dist",
    });
  });
});
