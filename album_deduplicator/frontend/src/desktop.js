const fallbackRuntime = {
  isElectron: false,
  backendBaseUrl: import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000",
  version: null,
  platform: typeof navigator !== "undefined" ? navigator.platform : "web",
};

function getBridge() {
  return typeof window !== "undefined" ? window.albumDeduplicator : null;
}

export function getRuntimeSnapshot() {
  const bridge = getBridge();
  if (bridge?.runtime?.backendBaseUrl) {
    return bridge.runtime;
  }
  return fallbackRuntime;
}

export async function getRuntimeInfo() {
  const bridge = getBridge();
  if (bridge?.getRuntimeInfo) {
    return bridge.getRuntimeInfo();
  }
  return fallbackRuntime;
}

export async function pickScanFolders() {
  const bridge = getBridge();
  if (!bridge?.selectScanFolders) {
    return [];
  }
  return bridge.selectScanFolders();
}

export async function pickPreferredRoot() {
  const bridge = getBridge();
  if (!bridge?.selectPreferredRoot) {
    return null;
  }
  return bridge.selectPreferredRoot();
}

export async function openDesktopPath(targetPath) {
  const bridge = getBridge();
  if (!bridge?.openPath) {
    return false;
  }
  const result = await bridge.openPath(targetPath);
  if (!result?.ok) {
    throw new Error(result?.error || "Failed to open the selected path.");
  }
  return true;
}
