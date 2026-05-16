import { describe, expect, it } from "vitest";

import appVersionModule from "./app-version.cjs";

const { getGitTagVersion, parseVersionFromTag, resolveAppVersion } = appVersionModule;

describe("app version resolver", () => {
  it("extracts a semantic version from the release tag", () => {
    expect(parseVersionFromTag("album-deduplicator-v1.2.3")).toBe("1.2.3");
    expect(parseVersionFromTag("album-deduplicator-v1.2.3-beta.1")).toBe("1.2.3-beta.1");
    expect(parseVersionFromTag("other-tag-v1.2.3")).toBeNull();
  });

  it("fails fast for an invalid release tag format", () => {
    expect(() => parseVersionFromTag("album-deduplicator-vnext")).toThrow(/Invalid Album Deduplicator version/);
  });

  it("prefers an explicit environment override", () => {
    expect(resolveAppVersion({
      env: {
        ALBUM_DEDUP_VERSION: "3.4.5",
        GITHUB_REF_NAME: "album-deduplicator-v1.2.3",
      },
      gitTagVersion: "2.0.0",
      packageVersion: "0.1.0",
    })).toBe("3.4.5");
  });

  it("uses the GitHub tag name when present", () => {
    expect(resolveAppVersion({
      env: { GITHUB_REF_NAME: "album-deduplicator-v1.2.3" },
      gitTagVersion: null,
      packageVersion: "0.1.0",
    })).toBe("1.2.3");
  });

  it("uses an exact local git tag when no CI tag is present", () => {
    expect(resolveAppVersion({
      env: {},
      gitTagVersion: "2.5.0",
      packageVersion: "0.1.0",
    })).toBe("2.5.0");
  });

  it("falls back to package.json version outside a tagged release", () => {
    expect(resolveAppVersion({
      env: {},
      gitTagVersion: null,
      packageVersion: "0.1.0",
    })).toBe("0.1.0");
  });

  it("ignores missing git metadata and returns null", () => {
    expect(getGitTagVersion({
      execFileSyncImpl: () => {
        const error = new Error("git not found");
        error.code = "ENOENT";
        throw error;
      },
    })).toBeNull();
  });
});
