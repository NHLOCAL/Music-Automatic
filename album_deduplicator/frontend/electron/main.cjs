const { app, BrowserWindow, dialog, ipcMain, shell } = require("electron");
const { spawn } = require("node:child_process");
const net = require("node:net");
const path = require("node:path");

const ELECTRON_DEV_URL = process.env.ELECTRON_RENDERER_URL || "http://127.0.0.1:5173";
const BACKEND_HOST = "127.0.0.1";
const BACKEND_START_TIMEOUT_MS = 30_000;

let backendProcess = null;
let backendBaseUrl = null;
let mainWindow = null;

function isDev() {
  return !app.isPackaged;
}

function logBackendOutput(stream, label) {
  stream.on("data", (chunk) => {
    const text = chunk.toString().trim();
    if (text) {
      console.log(`[backend:${label}] ${text}`);
    }
  });
}

function getBackendSourceRoot() {
  if (app.isPackaged) {
    return path.join(process.resourcesPath, "backend-source");
  }
  return path.resolve(__dirname, "..", "..");
}

function getPackagedBackendExecutable() {
  const extension = process.platform === "win32" ? ".exe" : "";
  return path.join(process.resourcesPath, "backend", `album-deduplicator-api${extension}`);
}

function getSpawnCandidates(port) {
  const sourceRoot = getBackendSourceRoot();
  const sharedArgs = [
    "-m",
    "uvicorn",
    "api.app:app",
    "--host",
    BACKEND_HOST,
    "--port",
    String(port),
  ];

  const candidates = [];
  const packagedExecutable = getPackagedBackendExecutable();
  candidates.push({
    command: packagedExecutable,
    args: [],
    cwd: path.dirname(packagedExecutable),
    mode: "packaged-executable",
  });

  const rawCommands = process.platform === "win32"
    ? [process.env.ALBUM_DEDUP_PYTHON, process.env.PYTHON, "py", "python"]
    : [process.env.ALBUM_DEDUP_PYTHON, process.env.PYTHON, "python3", "python"];

  const seen = new Set();
  rawCommands.filter(Boolean).forEach((command) => {
    const args = command === "py" ? ["-3", ...sharedArgs] : sharedArgs;
    const key = `${command}::${args.join(" ")}`;
    if (!seen.has(key)) {
      seen.add(key);
      candidates.push({
        command,
        args,
        cwd: sourceRoot,
        mode: "python-source",
      });
    }
  });

  return candidates;
}

function getFreePort() {
  return new Promise((resolve, reject) => {
    const server = net.createServer();
    server.unref();
    server.on("error", reject);
    server.listen(0, BACKEND_HOST, () => {
      const address = server.address();
      const port = typeof address === "object" && address ? address.port : null;
      server.close((closeError) => {
        if (closeError) {
          reject(closeError);
          return;
        }
        resolve(port);
      });
    });
  });
}

async function waitForBackend(url, timeoutMs) {
  const startedAt = Date.now();
  while (Date.now() - startedAt < timeoutMs) {
    try {
      const response = await fetch(`${url}/api/health`);
      if (response.ok) {
        return;
      }
    } catch (error) {
      // Ignore connection errors until timeout.
    }
    await new Promise((resolve) => setTimeout(resolve, 300));
  }
  throw new Error(`Backend did not become ready within ${timeoutMs}ms.`);
}

function stopBackend() {
  if (!backendProcess || backendProcess.killed) {
    return;
  }

  const pid = backendProcess.pid;
  if (process.platform === "win32") {
    spawn("taskkill", ["/pid", String(pid), "/t", "/f"], {
      windowsHide: true,
      stdio: "ignore",
    });
  } else {
    backendProcess.kill("SIGTERM");
  }
  backendProcess = null;
}

async function startBackend() {
  const port = await getFreePort();
  const url = `http://${BACKEND_HOST}:${port}`;
  const candidates = getSpawnCandidates(port);
  let lastError = null;

  for (const candidate of candidates) {
    try {
      const child = spawn(candidate.command, candidate.args, {
        cwd: candidate.cwd,
        env: {
          ...process.env,
          PYTHONIOENCODING: "utf-8",
          PYTHONUTF8: "1",
        },
        stdio: ["ignore", "pipe", "pipe"],
        windowsHide: true,
      });

      backendProcess = child;
      logBackendOutput(child.stdout, "stdout");
      logBackendOutput(child.stderr, "stderr");

      const exited = new Promise((_, reject) => {
        child.once("exit", (code, signal) => {
          reject(new Error(`Backend exited early (${candidate.mode}) with code=${code} signal=${signal}`));
        });
        child.once("error", reject);
      });

      await Promise.race([waitForBackend(url, BACKEND_START_TIMEOUT_MS), exited]);
      backendBaseUrl = url;
      return url;
    } catch (error) {
      lastError = error;
      stopBackend();
    }
  }

  throw lastError || new Error("Unable to launch backend.");
}

function setupIpcHandlers() {
  ipcMain.handle("desktop:get-runtime", () => ({
    isElectron: true,
    backendBaseUrl,
    version: app.getVersion(),
    platform: process.platform,
  }));

  ipcMain.handle("desktop:pick-scan-folders", async (_event, options = {}) => { 
    const defaultPath = typeof options.defaultPath === "string" && options.defaultPath.trim() 
      ? options.defaultPath.trim() 
      : undefined; 
    const allowMultiple = options.allowMultiple !== false;
    const title = allowMultiple ? "בחר תיקיות לסריקה" : "בחר תיקייה לסריקה";
    const buttonLabel = allowMultiple ? "הוסף תיקיות" : "בחר תיקייה";
    const properties = allowMultiple ? ["openDirectory", "multiSelections"] : ["openDirectory"];
 
    const result = await dialog.showOpenDialog(mainWindow, { 
      title, 
      buttonLabel, 
      defaultPath, 
      properties, 
    }); 
    return result.canceled ? [] : result.filePaths; 
  }); 

  ipcMain.handle("desktop:pick-preferred-root", async () => {
    const result = await dialog.showOpenDialog(mainWindow, {
      title: "בחר תיקייה מועדפת לשמירה",
      properties: ["openDirectory"],
    });
    return result.canceled ? null : (result.filePaths[0] || null);
  });

  ipcMain.handle("desktop:open-path", async (_event, targetPath) => {
    const error = await shell.openPath(targetPath);
    return { ok: !error, error: error || null };
  });

  ipcMain.handle("desktop:reveal-path", async (_event, targetPath) => {
    shell.showItemInFolder(targetPath);
    return { ok: true };
  });
}

async function createMainWindow() {
  mainWindow = new BrowserWindow({
    width: 1600,
    height: 980,
    minWidth: 1280,
    minHeight: 820,
    show: false,
    backgroundColor: "#f4f1ea",
    title: "Music Automatic",
    webPreferences: {
      preload: path.join(__dirname, "preload.cjs"),
      contextIsolation: true,
      nodeIntegration: false,
      additionalArguments: [
        `--backend-base-url=${backendBaseUrl}`,
        `--app-version=${app.getVersion()}`,
      ],
    },
  });

  mainWindow.once("ready-to-show", () => {
    mainWindow.show();
  });

  mainWindow.on("closed", () => {
    mainWindow = null;
  });

  if (isDev()) {
    await mainWindow.loadURL(ELECTRON_DEV_URL);
    mainWindow.webContents.openDevTools({ mode: "detach" });
    return;
  }

  await mainWindow.loadURL(`${backendBaseUrl}/`);
}

app.on("window-all-closed", () => {
  stopBackend();
  if (process.platform !== "darwin") {
    app.quit();
  }
});

app.on("before-quit", () => {
  stopBackend();
});

app.whenReady().then(async () => {
  try {
    await startBackend();
    setupIpcHandlers();
    await createMainWindow();
  } catch (error) {
    console.error(error);
    dialog.showErrorBox(
      "Album Deduplicator failed to start",
      `${error.message}\n\nודא ש-Python זמין במערכת ושה-dependencies של ה-backend מותקנות.`,
    );
    app.quit();
  }
});
