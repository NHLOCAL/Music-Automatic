const crypto = require("node:crypto");
const os = require("node:os");

function sanitizeFilenamePart(value, fallback) {
  const cleaned = String(value || "")
    .trim()
    .replace(/[<>:"/\\|?*\x00-\x1f]+/g, "-")
    .replace(/\s+/g, "-")
    .replace(/-+/g, "-")
    .replace(/^-|-$/g, "")
    .slice(0, 40);
  return cleaned || fallback;
}

function formatTimestamp(date = new Date()) {
  return date.toISOString().replace(
    /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2}).*$/,
    "$1$2$3-$4$5$6",
  );
}

function buildFeedbackExportFilename({
  date = new Date(),
  username = os.userInfo().username,
  hostname = os.hostname(),
  randomId = crypto.randomBytes(3).toString("hex"),
} = {}) {
  const safeUser = sanitizeFilenamePart(username, "user");
  const safeHost = sanitizeFilenamePart(hostname, "machine");
  const safeId = sanitizeFilenamePart(randomId, "export");
  return `ma-feedback_${formatTimestamp(date)}_${safeUser}-${safeHost}_${safeId}.jsonl`;
}

module.exports = {
  buildFeedbackExportFilename,
  formatTimestamp,
  sanitizeFilenamePart,
};
