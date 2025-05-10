// 4. renderer.js - Script del processo renderer
// File: renderer.js
/*+
The ipcRenderer module is an EventEmitter. It provides a few methods so it can be sent
synchronous and asynchronous messages from the render process (web page) to the main process.
You can also receive replies from the main process.
 */
const { ipcRenderer } = require('electron');

//DOM's elements
const searchInput = document.getElementById('searchInput');
const clearSearchBtn = document.getElementById('clearSearch');
const resultsList = document.getElementById('resultsList');
const initialMessage = document.getElementById('initialMessage');
const noResults = document.getElementById('noResults');

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

//Show/hide clear button on search input
searchInput.addEventListener('input', ()=>{
  clearSearchBtn.style.display = searchInput.value ? 'block': 'none';
})
// listen the message to put the focus on the input when the window is shown
ipcRenderer.on('focus-search', () => {
  searchInput.focus();
  searchInput.select(); // selects all the text written in the input
});

//That means the app watches for any input, when it sees one,
// it runs the function specified

searchInput.addEventListener('keydown', (e)=>{
  if(e.key === 'Enter') {
    //user pressed enter
    const query = searchInput.value.trim();

    //it executes the query in the backend
    if(query){
      /*const resultsList = document.getElementById('results');
      resultsList.innerHTML='<p>Searching for results..</p>';*/
      resultsList.innerHTML = `
      <li class="result-item">
        <div class="item-icon">🔎</div>
        <div class="item-details">
          <p class="item-name">Ricerca in corso...</p>
          <p class="item-type">Attendi i risultati</p>
        </div>
      </li>
    `;
      //sending the query to the backend
      ipcRenderer.send('execute-search', query);
    }
  }
})

 ipcRenderer.on('search-results', (event, results) => {
  //listens for results
   displayResults(results);
 })

  // updates the UI
  initialMessage.style.display = 'none';
  displayResults(results);

//to clear the research
clearSearchBtn.addEventListener('click', () => {
  searchInput.value = '';
  searchInput.focus();
  clearSearchBtn.style.display = 'none';
  resultsList.innerHTML = '';
  initialMessage.style.display = 'block';
  noResults.style.display = 'none';
});

//escape to close
document.addEventListener('keydown', (e) => {
  if (e.key === 'Escape') {
    window.close(); // closes the window
  }
});
function getFileIcon(filename){
  const ext = filename.split('.').pop().toLowerCase();
  return extensionIcons[ext] || extensionIcons['default'];
}

function getFileExtension(filename) {
  return filename.split('.').pop().toLowerCase();
}

//shows results of the research
function displayResults(results) {
   //reset
  resultsList.innerHTML = '';
  initialMessage.style.display = 'none';
  noResults.style.display = 'none';

  if(results.length === 0) {
    noResults.style.display = 'block';
    return;
  }
  results.forEach(filePath => {
    const filename = filePath.split(/[\\/]/).pop(); //extract filename
    const icon = getFileIcon(filename);
    const ext = getFileExtension(filename);

    const li = document.createElement('li');
    li.className = 'result-item';
    li.innerHTML = `
      <div class="item-icon">${icon}</div>
      <div class="item-details">
        <p class="item-name">${filename}</p>
        <p class="item-type">${getFileExtension(filename).toUpperCase()} file</p>
      </div>
    `;

    li.addEventListener('click', () => {
      ipcRenderer.send('open-file', filePath);
    });
    resultsList.appendChild(li);
  });
}