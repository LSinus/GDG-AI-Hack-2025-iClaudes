// 1. main.js - Processo principale di Electron
const { app, BrowserWindow, globalShortcut, screen, ipcMain, shell } = require('electron');
const path = require('path');
const fs = require('fs');
const os = require('os');

// Variabile per tenere traccia della finestra principale
let mainWindow = null;
let isVisible = false;

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
      nodeIntegration: true,
      contextIsolation: false
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
}



// Quando l'app è pronta
app.whenReady().then(() => {
  createWindow();

  // Registra lo shortcut globale Cmd+Space o Ctrl+Space
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

ipcMain.on('execute-search', (event, query) => {
  //executing query in the backend ...
  //....
  //results from the backend
  const results = ["/Users/giorgiasavo/Documents/projects/personal/TiW_perMe/codehal/style.css", "/Users/giorgiasavo/Downloads/06_dinamicaSistMecc.pdf"];
  event.reply('search-results', results); //send results back to renderer
});



//each results can be opened
ipcMain.on('open-file', (event, filePath) => {
  console.log('Attempting to open file:', filePath);
  fs.access(filePath, fs.constants.F_OK, (err) => {
    if(err){
      console.error('File does not exist');
      return;
    }

    shell.openPath(filePath)
      .then(result =>{
        if(result){
          console.error('Error opening file:', result);
        }else{
          console.log('File opened succesfully!');
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

app.on('window-all-closed', () =>{
  if(process.platform !== 'darwin') app.quit();
});

app.on('before-quit', () => {
  app.isQuitting = true;
});