# User Query Flow Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                                FRONTEND                                     │
│                               (script.js)                                   │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                         1. User types query & clicks Send
                                    │
                              ┌─────────────┐
                              │sendMessage()│
                              └─────────────┘
                                    │
                         2. POST /api/query
                            { query, session_id }
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              BACKEND API                                    │
│                                (app.py)                                     │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                         3. FastAPI endpoint validates request
                                    │
                              ┌────────────┐
                              │QueryRequest│
                              └────────────┘
                                    │
                         4. Create/get session_id
                                    │
                         5. Call rag_system.query()
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                            RAG SYSTEM                                       │
│                          (rag_system.py)                                    │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                         6. Build AI prompt with query
                                    │
                         7. Get conversation history
                                    │
                         8. Call AI generator with tools
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           AI GENERATOR                                      │
│                         (ai_generator.py)                                   │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                         9. Send to Claude API with system prompt
                            & tool definitions
                                    │
                        ┌─────────────────────────┐
                        │ Does Claude need tools? │
                        └─────────────────────────┘
                                    │
                           ┌────────┴────────┐
                           │                 │
                          YES               NO
                           │                 │
                           ▼                 ▼
                    ┌──────────────┐   ┌──────────────┐
                    │  Tool Usage  │   │ Direct Answer│
                    │              │   │              │
                    │      ▼       │   │      ▼       │
┌─────────────────────────────────────────────────────────────────────────────┐
│                          SEARCH TOOLS                                       │
│                        (search_tools.py)                                    │
└─────────────────────────────────────────────────────────────────────────────┘
                    │              │   │              │
         10. Execute│search_course_│   │              │
            tool    │content()     │   │              │
                    │      ▼       │   │              │
┌─────────────────────────────────────────────────────────────────────────────┐
│                         VECTOR STORE                                        │
│                        (vector_store.py)                                    │
└─────────────────────────────────────────────────────────────────────────────┘
                    │              │   │              │
        11. Semantic│search in     │   │              │
            ChromaDB│with filters  │   │              │
                    │      ▼       │   │              │
┌─────────────────────────────────────────────────────────────────────────────┐
│                           DATABASE                                          │
│                          (ChromaDB)                                         │
└─────────────────────────────────────────────────────────────────────────────┘
                    │              │   │              │
         12. Return │relevant      │   │              │
             chunks │+ metadata    │   │              │
                    │      ▲       │   │              │
                    └──────┼───────┘   └──────────────┘
                           │
         13. Format results with course/lesson context
                           │
         14. Track sources for UI display
                           │
         15. Return formatted content to AI
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           AI GENERATOR                                      │
│                         (ai_generator.py)                                   │
└─────────────────────────────────────────────────────────────────────────────┘
                           │
         16. Claude generates final response using tool results
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                            RAG SYSTEM                                       │
│                          (rag_system.py)                                    │
└─────────────────────────────────────────────────────────────────────────────┘
                           │
         17. Collect sources from tool manager
                           │
         18. Update session with conversation
                           │
         19. Return (response, sources)
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              BACKEND API                                    │
│                               (app.py)                                      │
└─────────────────────────────────────────────────────────────────────────────┘
                           │
         20. Create QueryResponse model
             { answer, sources, session_id }
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                                FRONTEND                                     │
│                              (script.js)                                    │
└─────────────────────────────────────────────────────────────────────────────┘
                           │
         21. Remove loading message
                           │
         22. Render response with markdown
                           │
         23. Display sources in collapsible section
                           │
         24. Re-enable input for next query
                           │
                           ▼
                    ┌──────────────┐
                    │ User sees    │
                    │ answer +     │
                    │ sources      │
                    └──────────────┘

═══════════════════════════════════════════════════════════════════════════════

Key Components:

🌐 FRONTEND:     User interface, handles input/display
🔌 API LAYER:    FastAPI endpoints, request validation  
🎯 RAG SYSTEM:   Main orchestrator, manages flow
🤖 AI GENERATOR: Claude API integration, tool execution
🔍 SEARCH TOOLS: Course content search with filtering
💾 VECTOR STORE: ChromaDB semantic search interface
📊 DATABASE:     ChromaDB vector storage

Flow Characteristics:
• Tool-driven: AI decides when to search based on query
• Session-aware: Maintains conversation context  
• Source tracking: UI shows which courses informed answer
• Error handling: Graceful fallbacks at each layer
• Async UX: Loading states provide immediate feedback
```