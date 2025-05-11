// File: preload.js
const { contextBridge, ipcRenderer } = require('electron');

// Expose protected methods that allow the renderer process to use
// the ipcRenderer without exposing the entire object
contextBridge.exposeInMainWorld(
  'electronAPI', {
    focusSearch: (callback) => ipcRenderer.on('focus-search', callback),
    searchResults: (callback) => ipcRenderer.on('search-results', callback),
    socketStatus: (callback) => ipcRenderer.on('socket-status', callback),
    searchStatus: (callback) => ipcRenderer.on('search-status', callback),
    hideWindow: () => ipcRenderer.send('hide-window'),
    executeSearch: (query) => ipcRenderer.send('execute-search', query),
    openFile: (path) => ipcRenderer.send('open-file', path),
    cancelSearch: () => ipcRenderer.send('cancel-search')
  }
);

window.addEventListener('DOMContentLoaded', () => {
  console.log('DOM fully loaded and parsed');

  // Check if SpeechRecognition is available
  if (!window.SpeechRecognition && !window.webkitSpeechRecognition) {
    console.warn('SpeechRecognition API is not available in this Electron environment');
  } else {
    console.log('SpeechRecognition API is available');
  }
});