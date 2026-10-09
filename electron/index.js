const { app, BrowserWindow, ipcMain, dialog } = require('electron');
const { spawn } = require('child_process');
const crypto = require('crypto');
const net = require('net');
const path = require('path');

let backend = null;          // child process
let backendConfig = null;    // { port, token, baseUrl }
let mainWindow = null;

// Tries to create a server to see if a port is available
function getFreePort() {
  return new Promise((resolve, reject) => {
    const srv = net.createServer();
    srv.unref();
    srv.on('error', reject);
    srv.listen(0, '127.0.0.1', () => {
      const { port } = srv.address();
      srv.close(() => resolve(port));
    });
  });
}

function resolveBackendCommand() {
  if (app.isPackaged) {
    // frozen binary shipped through electron-builder's extraResources
    const exe = process.platform === 'win32' ? 'rlgym-backend.exe' : 'rlgym-backend';
    return { cmd: path.join(process.resourcesPath, 'backend', exe), args: [], cwd: process.resourcesPath };
  }
  // dev: run from the venv inside rlgym-api
  const apiDir = path.join(__dirname, '..', 'rlgym-server');
  const venvPython = process.platform === 'win32'
    ? path.join(apiDir, '.venv', 'Scripts', 'python.exe')
    : path.join(apiDir, '.venv', 'bin', 'python');
  return {
    cmd: process.env.RLGYM_PYTHON || venvPython,
    args: ['main.py'],
    cwd: apiDir,
  };
}

async function waitForBackend(config, timeoutMs = 20000) {
  const start = Date.now();
  while (Date.now() - start < timeoutMs) {
    if (!backend) throw new Error('Backend process exited before becoming ready');
    try {
      const res = await fetch(`${config.baseUrl}/health`, {
        headers: { 'X-Api-Token': config.token },
      });
      if (res.ok) return;
    } catch (_) { /* not up yet */ }
    await new Promise((r) => setTimeout(r, 250));
  }
  throw new Error('Backend did not become ready in time');
}

async function startBackend() {
  const port = await getFreePort();
  const token = crypto.randomBytes(16).toString('hex');
  backendConfig = { port, token, baseUrl: `http://127.0.0.1:${port}` };

  const { cmd, args, cwd } = resolveBackendCommand();
  backend = spawn(cmd, args, {
    cwd,
    windowsHide: true,
    env: {
      ...process.env,
      RLGYM_GUI_PORT: String(port),
      RLGYM_GUI_TOKEN: token,
      RLGYM_GUI_DATA_DIR: app.getPath('userData'),
      RLGYM_GUI_VERSION: app.getVersion(),
    },
  });

  backend.stdout.on('data', (d) => console.log(`[backend] ${d}`));
  backend.stderr.on('data', (d) => console.error(`[backend] ${d}`));
  backend.on('error', (err) => console.error('[backend] failed to spawn:', err));
  backend.on('exit', (code) => {
    console.log(`[backend] exited with code ${code}`);
    backend = null;
  });

  await waitForBackend(backendConfig);
}

function stopBackend() {
  return new Promise((resolve) => {
    if (!backend) return resolve();
    backend.once('exit', resolve);
    backend.kill();
    setTimeout(resolve, 5000); // don't hang forever
  });
}

// Error Handling
process.on('uncaughtException', (error) => {
    console.error("Unexpected error: ", error);
});
function createWindow() {
    mainWindow = new BrowserWindow({
        width: 800,
        height: 600,
        show: false,
        roundedCorners: true,
        autoHideMenuBar: true,
        webPreferences: {
            preload: path.join(__dirname, 'preload.js'),
            contextIsolation: true,
            enableRemoteModule: false,
        }
    });

    mainWindow.once('ready-to-show', () => mainWindow.show());

    if(app.isPackaged){
        mainWindow.loadFile(path.join(__dirname, 'renderer', 'browser', 'index.html'));
    }
    else{
        mainWindow.loadURL('http://localhost:4200');
    }
}

const gotLock = app.requestSingleInstanceLock();
if (!gotLock) {
  app.quit();
}
else {
    // Show current app if exe is reopened
  app.on('second-instance', () => {
    if (mainWindow) {
      if (mainWindow.isMinimized()) mainWindow.restore();
      mainWindow.focus();
    }
  });

  ipcMain.handle('backend:get-config', () => backendConfig);

  app.whenReady().then(async () => {
    try {
      await startBackend();
      createWindow();
      const { initUpdater } = require('./updater');

      const updater = initUpdater({
        getWindow: () => mainWindow,
        beforeInstall: stopBackend,
      });
      setTimeout(() => updater.check(), 5000);   // check shortly after launch, non-blocking
    } catch (err) {
      dialog.showErrorBox('RLGym GUI failed to start', String(err.message || err));
      stopBackend();
      app.quit();
    }
  });

  app.on('before-quit', stopBackend);
  app.on('window-all-closed', () => app.quit());
}
