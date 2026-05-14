import { describe, expect, it } from "vitest";

import filenameModule from "./feedback-export-filename.cjs";

const { buildFeedbackExportFilename, sanitizeFilenamePart } = filenameModule;

describe("feedback export filename", () => {
  it("builds a descriptive JSONL filename that distinguishes runs and machines", () => {
    const filename = buildFeedbackExportFilename({
      date: new Date("2026-05-15T12:34:56.000Z"),
      username: "me user",
      hostname: "studio-pc",
      randomId: "a1b2c3",
    });

    expect(filename).toBe("ma-feedback_20260515-123456_me-user-studio-pc_a1b2c3.jsonl");
  });

  it("sanitizes characters that are invalid in Windows filenames", () => {
    expect(sanitizeFilenamePart('a<b>c:d/e\\f|g?h*i', "fallback")).toBe("a-b-c-d-e-f-g-h-i");
  });
});
