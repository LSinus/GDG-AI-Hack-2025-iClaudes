# Flint: Intelligent File Search and Versioning System

## Overview

Flint is an advanced file management application designed to solve the complexities of searching and tracking files in large data systems. Traditional file search methods often fall short when users only remember fragments of content. Flint introduces an AI-powered solution that enables:

1. **Semantic File Search**: Find files based on meaning, not just keywords
2. **Automatic Version Tracking**: Trace file changes over time

## Key Features

- **Intuitive Search Interface**: Spotlight-like search window for quick file retrieval
- **Semantic Content Matching**: Uses AI to understand and match file contents
- **Automatic Versioning**: Tracks file changes using Git
- **Cross-Platform Support**: Electron-based desktop application

## System Architecture

### Frontend
- Built with Electron, providing a cross-platform desktop application
- Global shortcut support (e.g., Option+Space to show/hide search window)
- Secure communication between rendering and main processes

### Backend
- Python-based backend with comprehensive file management capabilities
- Integrates multiple technologies for intelligent file handling:
  - Redis for metadata and vector storage
  - Git for version control
  - Google Gemini for content analysis
  - SentenceTransformers for semantic embedding

### Key Technologies
- Python
- JavaScript
- Electron
- Redis
- Git
- Google Gemini
- SentenceTransformers
- Sockets

## Detailed Work Mechanism

### File Processing Workflow
1. **File Monitoring**: 
   - Uses Watchdog to continuously monitor a specified directory
   - Detects file creations, modifications, deletions, and moves

2. **Content Extraction and Summarization**:
   - Extracts text from various file types (DOCX, PDF, XLSX, PPTX) using custom agent
   - Generates concise, meaningful summaries using Google Gemini
   - Identifies key keywords and essential content

3. **Vector Embedding Generation**:
   - Utilizes SentenceTransformer model to convert file summaries into high-dimensional vector embeddings
   - Each file summary is transformed into a dense vector representation that captures semantic meaning
   - Embeddings enable semantic similarity searches beyond traditional keyword matching

4. **Redis Vector Storage**:
   - Stores vector embeddings in Redis Stack's vector search capability
   - Each file record contains:
     * Relative file path
     * Git commit hash
     * Textual summary
     * Vector embedding
   - Unique Redis key format: `{relative_path}:{commit_hash}`
   - Allows indexing and retrieving multiple versions of the same file

### Search Mechanism
1. **Query Processing**:
   - User enters a search query
   - Google Gemini analyzes and expands the query
   - Transforms query into a hypothetical document description

2. **Semantic Matching**:
   - Generates vector embedding for the expanded query
   - Performs vector similarity search in Redis
   - Uses vector distance calculations to find most relevant files
   - Ranks results based on semantic closeness

3. **Version Comparison**:
   - Utilizes `diff.py` to compare file versions
   - Determines significance of changes between file versions
   - Helps users track meaningful document modifications

## Search Workflow Visualization
```
User Query 
  ↓ (AI Expansion)
Hypothetical Document Description 
  ↓ (Vector Embedding)
High-Dimensional Vector 
  ↓ (Redis Vector Search)
Semantic File Matching 
  ↓ (Ranking)
Relevant File Results
```

### Key Vector Search Characteristics
- High-dimensional semantic representation
- Real-time similarity computation
- Multi-version file tracking
- Language and context-aware matching

## Team
Created by iClaudes team:
- [Leonardo Sinibaldi](https://github.com/LSinus) 
- [Simone Ranfoni](https://github.com/saevuss) 
- [Savo](https://github.com/gansimo) 
- [Marzia Favitta](https://github.com/marziafavitta)

Developed for GDG AI Hackathon - HCI Track
May 11, 2025