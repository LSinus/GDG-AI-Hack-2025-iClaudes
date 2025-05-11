// File: main.js - Processo principale di Electron (Modified for TCP Sockets with JSON)
const { app, BrowserWindow, globalShortcut, screen, ipcMain, shell, session } = require('electron');
const path = require('path');
const fs = require('fs');
const net = require('net'); // Use Node.js 'net' module for TCP

// --- TCP Configuration ---
const TCP_HOST = 'localhost'; // Hostname of your Python TCP server
const TCP_PORT = 30717;       // Port your Python TCP server is listening on
// -------------------------

// Variabile per tenere traccia della finestra principale
let mainWindow = null;
let isVisible = false;

// TCP Client Variables
let tcpClient = null;
let tcpConnected = false;
let receiveBuffer = ''; // Buffer for accumulating incoming TCP data

// Handle mic permission requests (remains the same)
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

// --- TCP Connection Logic ---
function connectTCP() {
  if (tcpClient && (tcpClient.connecting || tcpConnected)) {
    console.log('TCP client already connected or attempting to connect.');
    return;
  }

  console.log(`Attempting to connect to TCP server at ${TCP_HOST}:${TCP_PORT}`);
  if (tcpClient) { // Clean up any old instance
    tcpClient.destroy();
  }
  tcpClient = new net.Socket();
  
  // Set encoding for incoming data
  tcpClient.setEncoding('utf-8'); 
  
  // Set TCP_NODELAY option to avoid data buffering
  tcpClient.setNoDelay(true);

  tcpClient.connect(TCP_PORT, TCP_HOST, () => {
    console.log('TCP Connection Established with server.');
    tcpConnected = true;
    receiveBuffer = ''; // Reset buffer on new connection
    if (mainWindow) {
      mainWindow.webContents.send('tcp-status', { connected: true, message: 'Connected to server.' });
    }
  });

  tcpClient.on('data', (data) => {
    // Data is already decoded to string due to tcpClient.setEncoding('utf-8');
    console.log('Received raw TCP data:', data);
    parseAndForwardResults(data);
    console.log(document.location.pathname)
  });

  tcpClient.on('end', () => {
    console.log('TCP Connection: Server closed connection (FIN received).');
    tcpConnected = false;
    if (mainWindow) {
      mainWindow.webContents.send('tcp-status', { connected: false, message: 'Server closed connection.' });
    }
    if (tcpClient) {
      tcpClient.destroy();
      tcpClient = null;
    }
    
    // Try to reconnect after delay
    setTimeout(connectTCP, 5000);
  });

  // Rest of the event handlers (close, error) remain the same...
}

// --- Data Parsing Logic (for JSON from Python Backend) ---
function parseAndForwardResults(jsonString) {
  let fileResults = [];
  console.log("Attempting to parse JSON string from server:", jsonString);
  try {
    const trimmedJsonString = jsonString.trim();
    if (!trimmedJsonString) {
      console.warn("Received empty or whitespace-only string for JSON parsing. Skipping.");
      fileResults = [];
    } else {
      // Debug the raw string
      console.log("Raw trimmed string before parsing:", trimmedJsonString);
      
      // Try to parse the JSON
      const parsedData = JSON.parse(trimmedJsonString);
      console.log("Parsed data type:", typeof parsedData, "isArray:", Array.isArray(parsedData));
      
      if (Array.isArray(parsedData)) {
        fileResults = parsedData.filter(item => typeof item === 'string');
        console.log("Filtered file results:", fileResults);
        if (fileResults.length !== parsedData.length) {
          console.warn("Some items in the parsed JSON array were not strings and were filtered out.");
        }
      } else if (typeof parsedData === 'object' && parsedData !== null) {
        // Handle case where server returns an object with a results property
        if (Array.isArray(parsedData.results)) {
          fileResults = parsedData.results.filter(item => typeof item === 'string');
          console.log("Extracted results from object:", fileResults);
        } else {
          console.warn("Parsed JSON data is an object but doesn't contain a results array:", parsedData);
          fileResults = [];
        }
      } else {
        console.warn("Parsed JSON data is not an array or object. Received:", parsedData);
        fileResults = [];
      }
    }
  } catch (error) {
    console.error("Error parsing JSON from server:", error.message);
    console.error("Problematic JSON string received:", jsonString);
    
    // Try to recover if the JSON has some formatting issues
    try {
      // Check if the string might be wrapped in extra quotes
      if (jsonString.startsWith('"') && jsonString.endsWith('"')) {
        const unquotedString = jsonString.substring(1, jsonString.length - 1)
          .replace(/\\"/g, '"') // Replace escaped quotes
          .replace(/\\\\/g, '\\'); // Replace escaped backslashes
        
        console.log("Attempting to parse unquoted string:", unquotedString);
        const parsedData = JSON.parse(unquotedString);
        
        if (Array.isArray(parsedData)) {
          fileResults = parsedData.filter(item => typeof item === 'string');
          console.log("Successfully recovered by unquoting string:", fileResults);
        }
      }
    } catch (recoveryError) {
      console.error("Recovery attempt failed:", recoveryError.message);
      fileResults = [];
    }
  }

  // Ensure fileResults is always an array before sending to renderer
  if (!Array.isArray(fileResults)) {
    console.warn("fileResults is not an array. Setting to empty array.");
    fileResults = [];
  }
  
  console.log("Final parsed file results (from JSON):", fileResults);
  if (mainWindow) {
    mainWindow.webContents.send('search-results', fileResults);
  }
}


function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1200,
    height: 800,
    frame: false,
    transparent: true,
    resizable: false,
    show: false,
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      nodeIntegration: false,
      contextIsolation: true,
      enableRemoteModule: false,
      webSecurity: true,
      audioAutoplay: true
    }
  });

  mainWindow.loadFile('index.html');
  mainWindow.center();
  mainWindow.setAlwaysOnTop(true, 'floating');
  mainWindow.setVisibleOnAllWorkspaces(true);

  mainWindow.on('close', (event) => {
    if (!app.isQuitting) {
      event.preventDefault();
      mainWindow.hide();
      isVisible = false;
    }
    return false;
  });

  mainWindow.on('blur', () => {
    if (isVisible) {
      mainWindow.hide();
      isVisible = false;
    }
  });

  mainWindow.setVisibleOnAllWorkspaces(true, { visibleOnFullScreen: true });
  mainWindow.setAlwaysOnTop(true, 'floating');

  mainWindow.webContents.on('did-finish-load', () => {
    handlePermissionRequest();
  });
}

app.whenReady().then(() => {
  connectTCP();
  createWindow();

  globalShortcut.register('Option+Space', toggleSpotlight);

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
});

function toggleSpotlight() {
  if (isVisible) {
    mainWindow.hide();
    isVisible = false;
  } else {
    mainWindow.center();
    mainWindow.show();
    isVisible = true;
    mainWindow.webContents.send('focus-search');
  }
}

ipcMain.on('hide-window', () => {
  if (mainWindow) {
    mainWindow.hide();
    isVisible = false;
  }
});

ipcMain.on('execute-search', (event, query) => {
  if (!tcpClient || !tcpConnected) {
    console.warn('TCP client not connected. Cannot send search query.');
    if (event.sender) {
      event.sender.send('search-results', undefined);
      event.sender.send('tcp-status', {
        connected: false,
        message: 'Not connected to server. Please check connection.'
      });
    }
    return;
  }

  try {
    const messageToSend = query + '\n';
    // console.log(`Sending query via TCP: "${messageToSend.replace(/\n$/, "\\n")}"`);
    
    const success = tcpClient.write(messageToSend, 'utf-8', () => {
      // console.log('Query data flushed to kernel buffer.');
    });

    if (!success) {
      console.warn('TCP write buffer was full. Data may have been dropped or queued.');
    }
  } catch (error) {
    console.error('Error writing to TCP socket:', error);
    if (event.sender) {
      event.sender.send('tcp-status', {
        connected: tcpConnected,
        message: 'Error sending data to server.'
      });
    }
  }
});

ipcMain.on('open-file', (event, filePath) => {
  fs.access(filePath, fs.constants.F_OK, (err) => {
    if (err) {
      console.error("File access error for open-file:", err);
      return;
    }

    shell.openPath(filePath)
      .then(resultMessage => {
        if (resultMessage === '') {
          // console.log(`Successfully opened file: ${filePath}`);
          if (mainWindow) {
            mainWindow.hide();
            isVisible = false;
          }
        } else {
          console.error(`Failed to open file: ${filePath}. Message: ${resultMessage}`);
        }
      })
      .catch(err => {
        console.error("Error in shell.openPath:", err);
      });
  });
});

/*
ipcMain.on('cancel-search', (event) => {
  console.log("'cancel-search' IPC received, but no specific TCP implementation for it yet.");
});
*/

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    app.quit();
  }
});

app.on('before-quit', () => {
  console.log("Application is quitting...");
  app.isQuitting = true;
  if (tcpClient) {
    console.log("Destroying TCP client before quit.");
    tcpClient.destroy();
    tcpClient = null;
  }
});

process.on('unhandledRejection', (reason, promise) => {
  console.error('Unhandled Rejection at:', promise, 'reason:', reason);
});

process.on('uncaughtException', (error) => {
  console.error('Uncaught Exception:', error);
});