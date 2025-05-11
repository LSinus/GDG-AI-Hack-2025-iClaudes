// File: main.js - Processo principale di Electron
const { app, BrowserWindow, globalShortcut, screen, ipcMain, shell, session } = require('electron');
const path = require('path');
const fs = require('fs');
const io = require('socket.io-client')

// Variabile per tenere traccia della finestra principale
let mainWindow = null;
let isVisible = false;

let socket = null;

// Handle mic permission requests
function handlePermissionRequest() {
  session.defaultSession.setPermissionRequestHandler((webContents, permission, callback) => {
    if (permission === 'media') {
      // Always allow microphone access
      return callback(true);
    }

    // Deny all other permission requests
    return callback(false);
  });
}

// Connect to your backend socket server
function connectSocket() {
  // Replace with your actual backend socket URL
  const SOCKET_URL = 'http://localhost:30717';

  // Close any existing connection
  if (socket) {
    socket.close();
  }

  socket = io(SOCKET_URL, {
    reconnection: true,
    reconnectionAttempts: 5,
    reconnectionDelay: 1000,
    timeout: 10000
  });

  socket.on('connect', () => {
    // Notify the renderer process that the connection is successful
    if (mainWindow) {
      mainWindow.webContents.send('socket-status', { connected: true });
    }
  });

  socket.on('disconnect', () => {
    // Notify the renderer about disconnection
    if (mainWindow) {
      mainWindow.webContents.send('socket-status', { connected: false });
    }
    // Attempt to reconnect after a delay
    setTimeout(connectSocket, 5000);
  });

  socket.on('connect_error', (error) => {
    // Notify the renderer about the error
    if (mainWindow) {
      mainWindow.webContents.send('socket-status', {
        connected: false,
        error: error.message
      });
    }
  });

  // Listen for search results from the backend
  socket.on('search-results', (results) => {
    // Ensure results is an array of file paths
    const fileResults = Array.isArray(results) ? results : [];
    console.log("results received");
    // If the main window exists, forward the results to the renderer
    if (mainWindow) {
      mainWindow.webContents.send('search-results', fileResults);
      
    }
  });

  return socket;
}

function createWindow() {
  // Crea una finestra nascosta all'avvio
  const { width, height } = screen.getPrimaryDisplay().workAreaSize;

  mainWindow = new BrowserWindow({
    width: 1200,
    height: 800,
    frame: false,  // Rimuove la barra del titolo
    transparent: true,  // Rende la finestra trasparente
    resizable: false,
    show: false,  // Parte nascosta
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      nodeIntegration: false,  // For security, disable node integration
      contextIsolation: true,  // Enable context isolation for security
      enableRemoteModule: false, // Disable remote module for security
      webSecurity: true,
      // Enable audio for the window
      audioAutoplay: true
    }
  });

  // Carica il file HTML
  mainWindow.loadFile('index.html');

  // Centra la finestra
  mainWindow.center();

  // Mantieni la finestra sempre in primo piano quando visibile
  mainWindow.setAlwaysOnTop(true, 'floating');
  mainWindow.setVisibleOnAllWorkspaces(true);

  // Gestisci la chiusura della finestra (solo la nasconde)
  mainWindow.on('close', (event) => {
    if (!app.isQuitting) {
      event.preventDefault();
      mainWindow.hide();
      isVisible = false;
    }
    return false;
  });

  // Handle window blur - hide when clicking outside
  mainWindow.on('blur', () => {
    if (isVisible) {
      mainWindow.hide();
      isVisible = false;
    }
  });

  mainWindow.setVisibleOnAllWorkspaces(true, { visibleOnFullScreen: true });
  mainWindow.setAlwaysOnTop(true, 'floating');

  // For debugging
  mainWindow.webContents.on('did-finish-load', () => {
    // Initialize permission handling
    handlePermissionRequest();
  });
}

// Quando l'app è pronta
app.whenReady().then(() => {
  connectSocket();
  createWindow();

  // Registra lo shortcut globale Option+Space
  globalShortcut.register('Option+Space', toggleSpotlight);

  app.on('activate', () => {
    // Su macOS è comune ricreare una finestra quando
    // l'icona nel dock viene cliccata e non ci sono altre finestre aperte
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
});

// to show and hide the spotlight
function toggleSpotlight() {
  if (isVisible) {
    mainWindow.hide();
    isVisible = false;
  } else {
    // it shows the window in the center
    mainWindow.center();
    mainWindow.show();
    isVisible = true;
    // sends a message to render to put focus on input
    mainWindow.webContents.send('focus-search');
  }
}

// Hide window handler
ipcMain.on('hide-window', () => {
  mainWindow.hide();
  isVisible = false;
});

// Update the execute search IPC handler
ipcMain.on('execute-search', (event, query) => {
  // Check if socket is connected
  if (!socket || !socket.connected) {
    connectSocket();

    // Return a temporary "connecting" message
    event.sender.send('search-results', []);
    event.sender.send('socket-status', {
      connected: false,
      connecting: true
    });
    return;
  }

  //Emit the search query to the backend via socket
  socket.emit('perform-search', { query });
});

// Open file handler
ipcMain.on('open-file', (event, filePath) => {
  fs.access(filePath, fs.constants.F_OK, (err) => {
    if(err){
      return;
    }

    shell.openPath(filePath)
      .then(result => {
        if(!result) {
          // Hide spotlight after opening a file
          mainWindow.hide();
          isVisible = false;
        }
      })
      .catch(err => {
        // Silent error handling
      });
  });
});

// Handle app quit
app.on('window-all-closed', () => {
  if(process.platform !== 'darwin') app.quit();
});

app.on('before-quit', () => {
  app.isQuitting = true;
});

ipcMain.on('cancel-search', (event) => {
  if (socket && socket.connected) {
    socket.emit('cancel-search');
  }
});