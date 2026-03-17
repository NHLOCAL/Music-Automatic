const fs = require("node:fs");
const path = require("node:path");
const { execFileSync } = require("node:child_process");

const TAG_PREFIX = "album-deduplicator-v";
const SEMVER_PATTERN = /^\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?(?:\+[0-9A-Za-z.-]+)?$/;

function getPackageJsonPath() {
  return path.join(__dirname, "..", "package.json");
}

function normalizeVersion(version, source) {
  const cleanVersion = String(version ?? "").trim();
  if (!SEMVER_PATTERN.test(cleanVersion)) {
    throw new Error(`Invalid Album Deduplicator version from ${source}: "${cleanVersion}"`);
  }
  return cleanVersion;
}

function parseVersionFromTag(tagName) {
  const cleanTagName = String(tagName ?? "").trim();
  if (!cleanTagName) return null;
  if (!cleanTagName.startsWith(TAG_PREFIX)) return null;
  return normalizeVersion(cleanTagName.slice(TAG_PREFIX.length), `git tag ${cleanTagName}`);
}

function readPackageVersion(packageJsonPath = getPackageJsonPath()) {
  const packageJson = JSON.parse(fs.readFileSync(packageJsonPath, "utf8"));
  return normalizeVersion(packageJson.version, packageJsonPath);
}

function shouldIgnoreGitError(error) {
  if (!error) return false;
  if (error.code === "ENOENT") return true;
  return error.status === 128;
}

function getGitTagVersion({
  cwd = path.join(__dirname, ".."),
  execFileSyncImpl = execFileSync,
} = {}) {
  try {
    const output = execFileSyncImpl("git", ["tag", "--points-at", "HEAD"], {
      cwd,
      encoding: "utf8",
      stdio: ["ignore", "pipe", "pipe"],
    });
    const versions = output
      .split(/\r?\n/)
      .map((line) => line.trim())
      .filter(Boolean)
      .map(parseVersionFromTag)
      .filter(Boolean);

    const uniqueVersions = Array.from(new Set(versions));
    if (uniqueVersions.length > 1) {
      throw new Error(`Multiple Album Deduplicator release tags point at HEAD: ${uniqueVersions.join(", ")}`);
    }

    return uniqueVersions[0] ?? null;
  } catch (error) {
    if (shouldIgnoreGitError(error)) {
      return null;
    }
    throw error;
  }
}

function resolveAppVersion({
  env = process.env,
  packageJsonPath = getPackageJsonPath(),
  cwd = path.dirname(packageJsonPath),
  packageVersion,
  gitTagVersion,
  execFileSyncImpl = execFileSync,
} = {}) {
  if (env.ALBUM_DEDUP_VERSION) {
    return normalizeVersion(env.ALBUM_DEDUP_VERSION, "ALBUM_DEDUP_VERSION");
  }

  const githubTagVersion = parseVersionFromTag(env.GITHUB_REF_NAME);
  if (githubTagVersion) {
    return githubTagVersion;
  }

  const resolvedGitTagVersion = gitTagVersion !== undefined
    ? gitTagVersion
    : getGitTagVersion({ cwd, execFileSyncImpl });
  if (resolvedGitTagVersion) {
    return normalizeVersion(resolvedGitTagVersion, "git tag on HEAD");
  }

  return packageVersion !== undefined
    ? normalizeVersion(packageVersion, "package version override")
    : readPackageVersion(packageJsonPath);
}

if (require.main === module) {
  process.stdout.write(`${resolveAppVersion()}\n`);
}

module.exports = {
  TAG_PREFIX,
  getGitTagVersion,
  normalizeVersion,
  parseVersionFromTag,
  readPackageVersion,
  resolveAppVersion,
};
