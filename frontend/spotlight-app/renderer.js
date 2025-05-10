// 4. renderer.js - Script del processo renderer
// File: renderer.js
const { ipcRenderer } = require('electron');

// Elementi DOM
const searchInput = document.getElementById('searchInput');
const clearSearchBtn = document.getElementById('clearSearch');
const resultsList = document.getElementById('resultsList');
const initialMessage = document.getElementById('initialMessage');
const noResults = document.getElementById('noResults');

// Esempi di dati (in un'app reale potresti ottenerli dal file system)
const sampleData = [
  { id: 1, type: 'application', name: 'Browser', icon: '🌐' },
  { id: 2, type: 'application', name: 'Calendario', icon: '📅' },
  { id: 3, type: 'application', name: 'Calcolatrice', icon: '🧮' },
  { id: 4, type: 'file', name: 'Report Progetto.pdf', icon: '📄' },
  { id: 5, type: 'folder', name: 'Documenti', icon: '📁' },
  { id: 6, type: 'application', name: 'Orologio', icon: '⏰' },
  { id: 7, type: 'application', name: 'Musica', icon: '🎵' },
  { id: 8, type: 'application', name: 'Posta', icon: '✉️' },
];

// Ascolta il messaggio per mettere il focus sull'input quando la finestra viene mostrata
ipcRenderer.on('focus-search', () => {
  searchInput.focus();
  searchInput.select(); // Seleziona tutto il testo esistente
});

// Evento input per la ricerca in tempo reale
searchInput.addEventListener('input', () => {
  const query = searchInput.value.trim();

  // Mostra/nascondi il pulsante di cancellazione
  clearSearchBtn.style.display = query ? 'block' : 'none';

  if (!query) {
    // Pulisci i risultati se la query è vuota
    resultsList.innerHTML = '';
    initialMessage.style.display = 'block';
    noResults.style.display = 'none';
    return;
  }

  // Filtra i risultati
  const results = sampleData.filter(item =>
    item.name.toLowerCase().includes(query.toLowerCase())
  );

  // Aggiorna l'interfaccia in base ai risultati
  initialMessage.style.display = 'none';

  if (results.length === 0) {
    resultsList.innerHTML = '';
    noResults.style.display = 'block';
    noResults.textContent = `Nessun risultato trovato per "${query}"`;
  } else {
    noResults.style.display = 'none';
    displayResults(results);
  }
});

// Pulsante per cancellare la ricerca
clearSearchBtn.addEventListener('click', () => {
  searchInput.value = '';
  searchInput.focus();
  clearSearchBtn.style.display = 'none';
  resultsList.innerHTML = '';
  initialMessage.style.display = 'block';
  noResults.style.display = 'none';
});

// Tasto Escape per chiudere
document.addEventListener('keydown', (e) => {
  if (e.key === 'Escape') {
    window.close(); // Chiude la finestra
  }
});

// Mostra i risultati della ricerca
function displayResults(results) {
  resultsList.innerHTML = '';

  results.forEach(item => {
    const li = document.createElement('li');
    li.className = 'result-item';

    li.innerHTML = `
      <div class="item-icon">${item.icon}</div>
      <div class="item-details">
        <p class="item-name">${item.name}</p>
        <p class="item-type">${item.type}</p>
      </div>
    `;

    // Aggiunge evento click per eseguire l'elemento
    li.addEventListener('click', () => {
      ipcRenderer.send('execute-item', item);
    });

    resultsList.appendChild(li);
  });
}