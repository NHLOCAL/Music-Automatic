const { contextBridge, ipcRenderer } = require("electron");

function readArgument(prefix) {
  const entry = process.argv.find((value) => value.startsWith(prefix));
  return entry ? entry.slice(prefix.length) : "";
}

const runtime = Object.freeze({
  isElectron: true,
  backendBaseUrl: readArgument("--backend-base-url="),
  version: readArgument("--app-version="),
  platform: process.platform,
});

contextBridge.exposeInMainWorld("albumDeduplicator", {
  runtime,
  getRuntimeInfo: () => ipcRenderer.invoke("desktop:get-runtime"),
  selectScanFolders: () => ipcRenderer.invoke("desktop:pick-scan-folders"),
  selectPreferredRoot: () => ipcRenderer.invoke("desktop:pick-preferred-root"),
  openPath: (targetPath) => ipcRenderer.invoke("desktop:open-path", targetPath),
  revealPath: (targetPath) => ipcRenderer.invoke("desktop:reveal-path", targetPath),
});
