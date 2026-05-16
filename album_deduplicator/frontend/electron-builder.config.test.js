import { createRequire } from "node:module";
import { describe, expect, it } from "vitest";

const require = createRequire(import.meta.url);
const builderConfig = require("./electron-builder.config.cjs");

describe("electron builder config", () => {
  it("packages the ML model where the backend config resolves it", () => {
    expect(builderConfig.extraResources).toContainEqual({
      from: "../data/lgbm_regressor_model.joblib",
      to: "backend-source/data/lgbm_regressor_model.joblib",
    });
  });
});
