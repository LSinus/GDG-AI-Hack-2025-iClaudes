// File: renderer.js
// DOM elements
const searchInput = document.getElementById('searchInput');
const clearSearchBtn = document.getElementById('clearSearch');
const resultsList = document.getElementById('resultsList');
const initialMessage = document.getElementById('initialMessage');
const noResults = document.getElementById('noResults');
const spotlightContent = document.querySelector('.spotlight-content');
const spotlightContainer = document.querySelector('.spotlight-container');
const micButton = document.getElementById('micButton');

// Voice recognition variables
let recognition = null;
let isRecording = false;
let recognitionTimeout = null;

// File extension icons
const extensionIcons = {
  'pdf': '📄',
  'doc': '📝',
  'docx': '📝',
  'xls': '📊',
  'xlsx': '📊',
  'jpg': '🖼️',
  'jpeg': '🖼️',
  'png': '🖼️',
  'gif': '🖼️',
  'txt': '📄',
  'mp3': '🎵',
  'mp4': '🎬',
  'zip': '🗜️',
  'js': '📜',
  'html': '🌐',
  'css': '🎨',
  // fallback
  'default': '📁'
};

// Initialize speech recognition
function initSpeechRecognition() {
  // Check if browser supports speech recognition
  window.SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;

  if (!window.SpeechRecognition) {
    console.error('Speech recognition not supported by your browser');
    micButton.style.display = 'none';
    return;
  }

  //creating a rec instance
  try {
    recognition = new window.SpeechRecognition();
    recognition.continuous = false;
    recognition.interimResults = true;

    // Change to user's system language instead of forcing Italian
    // You can customize this or make it configurable
    recognition.lang = navigator.language || 'en-US'; // Use browser's language or default to English

    // Handle results
    recognition.onresult = (event) => {
      const transcript = Array.from(event.results)
          .map(result => result[0])
          .map(result => result.transcript)
          .join('');

      searchInput.value = transcript;
      clearSearchBtn.style.display = 'block';

      // If this is a final result
      if (event.results[0].isFinal) {
        console.log('Final transcript:', transcript);
      }
    };

    // Handle end of speech recognition
    recognition.onend = () => {
      isRecording = false;
      micButton.classList.remove('recording');
      searchInput.placeholder = 'Cerca o parla...';

      // If there's text, automatically execute search
      if (searchInput.value.trim()) {
        executeSearch(searchInput.value.trim());
      }
    };

    // Handle errors
    recognition.onerror = (event) => {
      console.error('Speech recognition error:', event.error);
      isRecording = false;
      micButton.classList.remove('recording');

      //If no speech detected, provide feedback
      if (event.error === 'no-speech') {
        searchInput.placeholder = 'No voice detected. Retry...';
        setTimeout(() => {
          searchInput.placeholder = 'Cerca o parla...';
        }, 2000);
      } else if (event.error === 'not-allowed' || event.error === 'permission-denied') {
        searchInput.placeholder = 'Microphone access denied';
        console.error('Microphone permission denied');
        setTimeout(() => {
          searchInput.placeholder = 'Cerca o parla...';
        }, 2000);
        micButton.disabled = true;
      }
    };

    console.log('Speech recognition initialized successfully');
  } catch(error) {
    console.error('Error initializing speech recognition:', error);
    micButton.style.display = 'none';
  }
}

// Toggle speech recognition
function toggleSpeechRecognition() {
  if (isRecording) {
    stopRecording();
  } else {
    startRecording();
  }
}

// Start recording
function startRecording() {
  // Ensure we stop any existing recognition session
  if (recognition && isRecording) {
    try {
      recognition.stop();
    } catch (e) {
      console.error('Error stopping existing recognition:', e);
    }
  }

  try {
    // Make sure the recognition object exists
    if (!recognition) {
      initSpeechRecognition();
    }

    // Start the recording
    recognition.start();
    console.log('Started recording');
    isRecording = true;
    micButton.classList.add('recording');
    searchInput.placeholder = 'Listening...';

    // Set a timeout to stop recording after 10 seconds if no speech detected
    if (recognitionTimeout) {
      clearTimeout(recognitionTimeout);
    }

    recognitionTimeout = setTimeout(() => {
      if (isRecording) {
        console.log('Recognition timeout - stopping');
        stopRecording();
      }
    }, 10000);
  } catch (error) {
    console.error('Error starting speech recognition:', error);
    stopRecording();
  }
}

// Stop recording
function stopRecording() {
  if (recognitionTimeout) {
    clearTimeout(recognitionTimeout);
    recognitionTimeout = null;
  }

  if (recognition && isRecording) {
    try {
      recognition.stop();
    } catch (error) {
      console.error('Error stopping speech recognition:', error);
    }
  }

  isRecording = false;
  micButton.classList.remove('recording');
  searchInput.placeholder = 'Cerca o parla...';
}

// Execute search
function executeSearch(query) {
  if (query) {
    resultsList.innerHTML = `
      <li class="result-item">
        <div class="item-icon"></div>
        <div class="item-details">
          <p class="item-name"></p>
          <p class="item-type"></p>
        </div>
      </li>
    `;
    // Send the query to the backend
    window.electronAPI.executeSearch(query);
  }
}

// Initialize voice recognition on startup - Wait for DOM to be fully loaded
document.addEventListener('DOMContentLoaded', () => {
  console.log('DOM loaded, initializing speech recognition');
  setTimeout(initSpeechRecognition, 500);
});

// Event listeners
micButton.addEventListener('click', (e) => {
  e.preventDefault();
  e.stopPropagation();
  console.log('Mic button clicked');
  toggleSpeechRecognition();
});

// Listen for focus on search input
window.electronAPI.focusSearch(() => {
  searchInput.focus();
  searchInput.select(); // Selects all text in the input
});

// Show/hide clear button on search input
searchInput.addEventListener('input', () => {
  clearSearchBtn.style.display = searchInput.value ? 'block' : 'none';
});

// Handle Enter key in search input
searchInput.addEventListener('keydown', (e) => {
  if (e.key === 'Enter') {
    const query = searchInput.value.trim();
    executeSearch(query);
  }
});

// Handle search results from main process
window.electronAPI.searchResults((event, results) => {
  console.log('Received results:', results);
  initialMessage.style.display = 'none';
  displayResults(results);
});

// Clear the search
clearSearchBtn.addEventListener('click', (e) => {
  e.stopPropagation();

  // Clear search input and reset UI
  searchInput.value = '';
  searchInput.focus();
  clearSearchBtn.style.display = 'none';
  resultsList.innerHTML = '';
  initialMessage.style.display = 'block';
  noResults.style.display = 'none';
});

// Handle Escape key to close window
document.addEventListener('keydown', (e) => {
  if (e.key === 'Escape') {
    // Stop recording if active
    if (isRecording) {
      stopRecording();
    }
    window.electronAPI.hideWindow();
  }
});

// Click outside to close spotlight
document.addEventListener('mousedown', (e) => {
  // If the click is on the container but not on the content, close the spotlight
  const wasClickInsideContent = spotlightContent.contains(e.target);
  if (!wasClickInsideContent) {
    console.log('Click outside detected, closing spotlight');
    // Stop recording if active
    if (isRecording) {
      stopRecording();
    }
    window.electronAPI.hideWindow();
  }
});

// Get file icon based on extension
function getFileIcon(filename) {
  const ext = filename.split('.').pop().toLowerCase();
  return extensionIcons[ext] || extensionIcons['default'];
}

// Get file extension
function getFileExtension(filename) {
  return filename.split('.').pop().toLowerCase();
}

// Display search results
function displayResults(results) {
  // Reset
  resultsList.innerHTML = '';
  initialMessage.style.display = 'none';
  noResults.style.display = 'none';

  if (!results || results.length === 0) {
    noResults.style.display = 'block';
    return;
  }

  results.forEach(filePath => {
    const filename = filePath.split(/[\\/]/).pop(); // Extract filename
    const icon = getFileIcon(filename);
    const ext = getFileExtension(filename);

    const li = document.createElement('li');
    li.className = 'result-item';
    li.innerHTML = `
      <div class="item-icon">${icon}</div>
      <div class="item-details">
        <p class="item-name">${filename}</p>
        <p class="item-type">${ext.toUpperCase()} file</p>
      </div>
    `;

    li.addEventListener('click', () => {
      console.log('File clicked:', filePath);
      window.electronAPI.openFile(filePath);
    });

    resultsList.appendChild(li);
  });
}