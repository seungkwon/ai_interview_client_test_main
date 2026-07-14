import { app, BrowserWindow } from "electron";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

function createWindow() {
  const win = new BrowserWindow({
    width: 1440,
    height: 960,
    minWidth: 1100,
    minHeight: 720,
    webPreferences: {
      preload: path.join(__dirname, "../preload/preload.js"),
      contextIsolation: true,
      nodeIntegration: false
    }
  });

  const rendererUrl = process.env.ELECTRON_RENDERER_URL ?? "http://localhost:5173";
  const bundledIndexPath = path.join(__dirname, "../../../dist/index.html");

  if (process.env.ELECTRON_RENDERER_URL) {
    win.loadURL(rendererUrl);
    return;
  }

  if (fs.existsSync(bundledIndexPath)) {
    win.loadFile(bundledIndexPath);
    return;
  }

  win.loadURL(rendererUrl);
}

function configureMediaPermissions() {
  const session = BrowserWindow.getAllWindows()[0]?.webContents.session ?? null;
  const defaultSession = session ?? undefined;
  if (!defaultSession) {
    return;
  }

  defaultSession.setPermissionCheckHandler((_webContents, permission) => {
    return permission === "media";
  });

  defaultSession.setPermissionRequestHandler((_webContents, permission, callback) => {
    callback(permission === "media");
  });
}

app.whenReady().then(() => {
  createWindow();
  configureMediaPermissions();

  app.on("activate", () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createWindow();
    }
  });
});

app.on("window-all-closed", () => {
  if (process.platform !== "darwin") {
    app.quit();
  }
});
