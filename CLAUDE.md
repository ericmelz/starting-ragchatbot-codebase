# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Essential Commands

### Development Environment Setup
```bash
# Install dependencies (uses uv package manager)
uv sync

# Start the development server 
./run.sh
# OR manually:
cd backend && uv run uvicorn app:app --reload --port 8000
```

### Environment Configuration
- Create `.env` file with `ANTHROPIC_API_KEY=your_key_here`
- Server runs on http://localhost:8000 (web interface and API docs at /docs)

### Database Management
- ChromaDB files stored in `./chroma_db/` directory
- Course documents are auto-loaded from `../docs/` on startup
- No explicit migration commands - vector DB rebuilds from source documents

## Architecture Overview

### RAG System Design
This is a **tool-based RAG system** where Claude AI decides when to search course materials. The flow differs from traditional RAG in that the AI has agency over when and how to retrieve information.

**Core Flow:**
1. User query → FastAPI endpoint → RAG System orchestrator
2. RAG System calls AI Generator with available search tools
3. Claude decides whether to use `search_course_content` tool based on query type
4. If search needed: Tool Manager → Vector Store → ChromaDB → formatted results back to Claude
5. Claude generates final response using retrieved context
6. Sources tracked and displayed in UI

### Key Architectural Components

**Document Processing Pipeline (`document_processor.py`):**
- Expects structured format: Course Title/Link/Instructor headers, then "Lesson N:" sections
- Sentence-based chunking with configurable overlap (800 chars, 100 char overlap)
- Enriches chunks with course/lesson context: "Course X Lesson Y content: [text]"

**Vector Storage (`vector_store.py`):**
- ChromaDB with `all-MiniLM-L6-v2` embeddings
- Stores both course metadata and content chunks
- Supports filtering by course name and lesson number
- Unified search interface with semantic course name matching

**Tool System (`search_tools.py`):**
- Extensible tool framework with abstract Tool base class
- `CourseSearchTool` provides semantic search with course/lesson filtering
- Tool Manager handles registration and execution
- Sources automatically tracked for UI display

**AI Integration (`ai_generator.py`):**
- Uses Claude Sonnet 4 with tool calling capability
- System prompt defines search tool usage patterns
- Handles tool execution flow and response assembly
- Temperature=0 for consistent responses

**Session Management (`session_manager.py`):**
- Maintains conversation history (configurable depth: 2 exchanges)
- Session-aware responses for context continuity

### Configuration Centralization
All settings in `backend/config.py` via dataclass with environment variable fallbacks:
- Model selection, chunk sizes, search limits
- Database paths, API keys
- Easily modified for different deployment environments

### Frontend Architecture
- Vanilla JavaScript with markdown rendering
- Async query handling with loading states  
- Real-time course statistics display
- Collapsible source attribution

### Key Design Principles
- **Tool-driven search**: AI decides when to search vs. use general knowledge
- **Context preservation**: Course/lesson metadata travels with text chunks
- **Source transparency**: UI shows which courses informed each answer  
- **Session continuity**: Conversation history maintained across exchanges
- **Flexible document structure**: Graceful handling of various course document formats
- Always use uv to run the server.  Do not use pip directly
- use uv to run python files
- use uv to manage all dependencies