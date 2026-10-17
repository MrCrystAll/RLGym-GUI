const { app, ipcMain } = require('electron');
const { autoUpdater } = require('electron-updater');
const log = require("electron-log")

function initUpdater({ getWindow, beforeInstall }) {
  autoUpdater.autoDownload = false;          // user decides when to download
  autoUpdater.autoInstallOnAppQuit = false;  // we control installation
  autoUpdater.logger = log;
  
  log.transports.file.level = "info";

  const send = (state) => getWindow()?.webContents.send('updater:state', state);

  autoUpdater.on('checking-for-update', () => send({ status: 'checking' }));
  autoUpdater.on('update-available', (info) => send({ status: 'available', ...release(info) }));
  autoUpdater.on('update-not-available', () => send({ status: 'up-to-date' }));
  autoUpdater.on('download-progress', (p) => send({ status: 'downloading', percent: Math.round(p.percent) }));
  autoUpdater.on('update-downloaded', (info) => send({ status: 'ready', ...release(info) }));
  autoUpdater.on('error', (err) => send({ status: 'error', message: err.message }));

  async function check() {
    if (!app.isPackaged) return send({ status: 'disabled' });
    try { await autoUpdater.checkForUpdates(); } catch (_) { /* reported by the 'error' event */ }
  }

  ipcMain.handle('updater:check', check);
  ipcMain.handle('updater:download', async () => {
    try { await autoUpdater.downloadUpdate(); } catch (_) {}
  });
  ipcMain.handle('updater:install', async () => {
    await beforeInstall();                   // stop the backend first
    autoUpdater.quitAndInstall();
  });

  return { check };
}

// The GitHub Release body (our changelog section) comes as HTML, or as one note per version when
// fullChangelog is on. The renderer sanitizes it before display.
function release(info) {
  const notes = Array.isArray(info.releaseNotes)
    ? info.releaseNotes.map((n) => n.note ?? '').join('')
    : info.releaseNotes;
  return { version: info.version, notes: notes || null, date: info.releaseDate ?? null };
}

module.exports = { initUpdater };