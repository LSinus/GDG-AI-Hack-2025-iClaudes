// File: main.js - Processo principale di Electron
const { app, BrowserWindow, globalShortcut, screen, ipcMain, shell, session } = require('electron');
const path = require('path');
const fs = require('fs');
const os = require('os');

// Variabile per tenere traccia della finestra principale
let mainWindow = null;
let isVisible = false;

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
    // Optional: Open DevTools for debugging
    // mainWindow.webContents.openDevTools({ mode: 'detach' });

    // Initialize permission handling
    handlePermissionRequest();
  });
}

// Quando l'app è pronta
app.whenReady().then(() => {
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

// Sample search function - you would replace this with your actual search logic
function searchFiles(query) {
  // Placeholder function - in a real app, you'd implement file system search here
  return [
    "/Users/giorgiasavo/Documents/projects/personal/TiW_perMe/codehal/style.css",
    "/Users/giorgiasavo/Downloads/06_dinamicaSistMecc.pdf"
  ];
}

// Hide window handler
ipcMain.on('hide-window', () => {
  mainWindow.hide();
  isVisible = false;
});

// Execute search
ipcMain.on('execute-search', (event, query) => {
  console.log('Executing search for:', query);

  // Here you would implement your actual search logic
  // For now, we'll use the example results
  const results = searchFiles(query);

  // Send results back to renderer
  event.sender.send('search-results', results);
});

// Open file handler
ipcMain.on('open-file', (event, filePath) => {
  console.log('Attempting to open file:', filePath);
  fs.access(filePath, fs.constants.F_OK, (err) => {
    if(err){
      console.error('File does not exist');
      return;
    }

    shell.openPath(filePath)
      .then(result => {
        if(result){
          console.error('Error opening file:', result);
        } else {
          console.log('File opened successfully!');
          // Hide spotlight after opening a file
          mainWindow.hide();
          isVisible = false;
        }
      })
      .catch(err => {
        console.error('Failed to open file: ', err)
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