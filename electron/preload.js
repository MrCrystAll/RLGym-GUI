const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('rlgym', {
  getBackendConfig: () => ipcRenderer.invoke('backend:get-config'),
  updater: {
  check: () => ipcRenderer.invoke('updater:check'),
  download: () => ipcRenderer.invoke('updater:download'),
  install: () => ipcRenderer.invoke('updater:install'),
  onState: (cb) => {
    const handler = (_e, state) => cb(state);
    ipcRenderer.on('updater:state', handler);
    return () => ipcRenderer.removeListener('updater:state', handler);
  },
},
});