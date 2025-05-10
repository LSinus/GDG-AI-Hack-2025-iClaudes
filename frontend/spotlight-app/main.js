// 1. main.js - Processo principale di Electron
const { app, BrowserWindow, globalShortcut, screen, ipcMain, shell } = require('electron');
const path = require('path');

// Variabile per tenere traccia della finestra principale
let mainWindow = null;
let isVisible = false;

function createWindow() {
  // Crea una finestra nascosta all'avvio
  const { width, height } = screen.getPrimaryDisplay().workAreaSize;

  mainWindow = new BrowserWindow({
    width: 600,
    height: 400,
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

  // Aggiunta debug (da rimuovere in produzione)
  // mainWindow.webContents.openDevTools();
}

// Quando l'app è pronta
app.whenReady().then(() => {
  createWindow();

  // Registra lo shortcut globale Cmd+Space o Ctrl+Space
  globalShortcut.register('CommandOrControl+Space', toggleSpotlight);

  app.on('activate', () => {
    // Su macOS è comune ricreare una finestra quando
    // l'icona nel dock viene cliccata e non ci sono altre finestre aperte
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
});

// Funzione per mostrare/nascondere il spotlight
function toggleSpotlight() {
  if (isVisible) {
    mainWindow.hide();
    isVisible = false;
  } else {
    // Mostra la finestra e la posiziona al centro
    mainWindow.center();
    mainWindow.show();
    isVisible = true;
    // Invia un messaggio al renderer per mettere il focus sull'input
    mainWindow.webContents.send('focus-search');
  }
}

// Chiudi l'app su tutte le piattaforme tranne macOS
app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit();
});

// Pulisci le scorciatoie globali quando l'app si chiude
app.on('will-quit', () => {
  globalShortcut.unregisterAll();
});

// Gestisci la richiesta di esecuzione di programmi o apertura di file
ipcMain.on('execute-item', (event, item) => {
  if (item.type === 'application') {
    // Qui puoi implementare il codice per avviare applicazioni
    // Esempio per macOS: exec(`open -a "${item.name}"`);
    // Esempio per Windows: exec(`start ${item.name}`);
    console.log(`Apertura applicazione: ${item.name}`);
  } else if (item.type === 'file') {
    // Apri il file
    shell.openPath(item.name);
  } else if (item.type === 'folder') {
    // Apri la cartella
    shell.openPath(item.name);
  }

  // Nascondi lo spotlight dopo aver selezionato un elemento
  mainWindow.hide();
  isVisible = false;
});