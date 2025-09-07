"""
Pytest configuration and shared fixtures for RAG system tests.
"""

import pytest
import tempfile
import os
import shutil
from unittest.mock import Mock, patch
from fastapi.testclient import TestClient

# Add parent directory to path for imports
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import Config
from vector_store import VectorStore
from search_tools import CourseSearchTool, CourseOutlineTool, ToolManager
from ai_generator import AIGenerator
from rag_system import RAGSystem
from models import Course, Lesson, CourseChunk


@pytest.fixture
def test_config():
    """Create a test configuration with safe defaults"""
    config = Config()
    config.MAX_RESULTS = 5  # Set to proper value for testing
    config.ANTHROPIC_API_KEY = "test-api-key"
    config.ANTHROPIC_MODEL = "claude-sonnet-4-20250514"
    config.EMBEDDING_MODEL = "all-MiniLM-L6-v2"
    config.CHUNK_SIZE = 800
    config.CHUNK_OVERLAP = 100
    config.MAX_HISTORY = 2
    return config


@pytest.fixture
def broken_config():
    """Create a config with MAX_RESULTS=0 to test the broken behavior"""
    config = Config()
    config.MAX_RESULTS = 0  # This is the broken setting causing issues
    config.ANTHROPIC_API_KEY = "test-api-key"
    config.ANTHROPIC_MODEL = "claude-sonnet-4-20250514"
    config.EMBEDDING_MODEL = "all-MiniLM-L6-v2"
    config.CHUNK_SIZE = 800
    config.CHUNK_OVERLAP = 100
    config.MAX_HISTORY = 2
    return config


@pytest.fixture
def temp_chroma_path():
    """Create a temporary directory for ChromaDB during tests"""
    temp_dir = tempfile.mkdtemp()
    yield temp_dir
    # Cleanup
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def test_vector_store(test_config, temp_chroma_path):
    """Create a VectorStore instance for testing with proper config"""
    test_config.CHROMA_PATH = temp_chroma_path
    return VectorStore(temp_chroma_path, test_config.EMBEDDING_MODEL, test_config.MAX_RESULTS)


@pytest.fixture
def broken_vector_store(broken_config, temp_chroma_path):
    """Create a VectorStore instance with the broken MAX_RESULTS=0 config"""
    broken_config.CHROMA_PATH = temp_chroma_path
    return VectorStore(temp_chroma_path, broken_config.EMBEDDING_MODEL, broken_config.MAX_RESULTS)


@pytest.fixture
def sample_course():
    """Create a sample course for testing"""
    lessons = [
        Lesson(lesson_number=1, title="Introduction to Testing", lesson_link="https://example.com/lesson1"),
        Lesson(lesson_number=2, title="Advanced Testing Concepts", lesson_link="https://example.com/lesson2"),
        Lesson(lesson_number=3, title="Integration Testing", lesson_link="https://example.com/lesson3"),
    ]
    return Course(
        title="Test Course",
        instructor="Test Instructor",
        course_link="https://example.com/course",
        lessons=lessons
    )


@pytest.fixture
def sample_course_chunks(sample_course):
    """Create sample course chunks for testing"""
    return [
        CourseChunk(
            course_title=sample_course.title,
            lesson_number=1,
            chunk_index=0,
            content="This is lesson 1 content about testing basics and fundamentals."
        ),
        CourseChunk(
            course_title=sample_course.title,
            lesson_number=1,
            chunk_index=1,
            content="More lesson 1 content covering test design patterns."
        ),
        CourseChunk(
            course_title=sample_course.title,
            lesson_number=2,
            chunk_index=2,
            content="Lesson 2 discusses advanced testing concepts like mocking and fixtures."
        ),
        CourseChunk(
            course_title=sample_course.title,
            lesson_number=3,
            chunk_index=3,
            content="Lesson 3 covers integration testing between different system components."
        )
    ]


@pytest.fixture
def populated_vector_store(test_vector_store, sample_course, sample_course_chunks):
    """Create a vector store populated with test data"""
    test_vector_store.add_course_metadata(sample_course)
    test_vector_store.add_course_content(sample_course_chunks)
    return test_vector_store


@pytest.fixture
def course_search_tool(populated_vector_store):
    """Create a CourseSearchTool with populated data"""
    return CourseSearchTool(populated_vector_store)


@pytest.fixture
def broken_course_search_tool(broken_vector_store, sample_course, sample_course_chunks):
    """Create a CourseSearchTool with the broken MAX_RESULTS=0 config"""
    # Still add data so we can test that the issue is MAX_RESULTS, not missing data
    broken_vector_store.add_course_metadata(sample_course)
    broken_vector_store.add_course_content(sample_course_chunks)
    return CourseSearchTool(broken_vector_store)


@pytest.fixture
def course_outline_tool(populated_vector_store):
    """Create a CourseOutlineTool with populated data"""
    return CourseOutlineTool(populated_vector_store)


@pytest.fixture
def tool_manager(course_search_tool, course_outline_tool):
    """Create a ToolManager with both tools registered"""
    manager = ToolManager()
    manager.register_tool(course_search_tool)
    manager.register_tool(course_outline_tool)
    return manager


@pytest.fixture
def mock_anthropic_client():
    """Mock Anthropic client for AI generator testing"""
    mock_client = Mock()
    mock_response = Mock()
    mock_response.content = [Mock()]
    mock_response.content[0].text = "Test AI response"
    mock_response.stop_reason = "end_turn"
    mock_client.messages.create.return_value = mock_response
    return mock_client


@pytest.fixture
def ai_generator_with_mock(test_config, mock_anthropic_client):
    """Create AIGenerator with mocked Anthropic client"""
    ai_gen = AIGenerator(test_config.ANTHROPIC_API_KEY, test_config.ANTHROPIC_MODEL)
    ai_gen.client = mock_anthropic_client
    return ai_gen


@pytest.fixture
def rag_system(test_config):
    """Create a RAGSystem instance for integration testing"""
    with patch('rag_system.VectorStore') as mock_vs, \
         patch('rag_system.AIGenerator') as mock_ai:
        
        # Mock the VectorStore and AIGenerator to avoid real API calls in integration tests
        mock_vector_store = Mock()
        mock_ai_generator = Mock()
        
        mock_vs.return_value = mock_vector_store
        mock_ai.return_value = mock_ai_generator
        
        rag = RAGSystem(test_config)
        rag.mock_vector_store = mock_vector_store  # Store references for test access
        rag.mock_ai_generator = mock_ai_generator
        
        return rag


@pytest.fixture
def test_app():
    """Create a FastAPI test app without static file mounting to avoid import issues"""
    from fastapi import FastAPI, HTTPException
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.middleware.trustedhost import TrustedHostMiddleware
    from pydantic import BaseModel
    from typing import List, Optional, Dict, Any
    
    # Create test app
    app = FastAPI(title="Test Course Materials RAG System")
    
    # Add middleware
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=["*"])
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Pydantic models
    class QueryRequest(BaseModel):
        query: str
        session_id: Optional[str] = None
    
    class ClearSessionRequest(BaseModel):
        session_id: str
    
    class QueryResponse(BaseModel):
        answer: str
        sources: List[Dict[str, Any]]
        session_id: str
    
    class CourseStats(BaseModel):
        total_courses: int
        course_titles: List[str]
    
    class ClearSessionResponse(BaseModel):
        success: bool
        message: str
    
    # Mock RAG system for testing
    mock_rag_system = Mock()
    
    @app.post("/api/query", response_model=QueryResponse)
    async def query_documents(request: QueryRequest):
        try:
            session_id = request.session_id or "test-session-id"
            answer, sources = mock_rag_system.query(request.query, session_id)
            return QueryResponse(answer=answer, sources=sources, session_id=session_id)
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.get("/api/courses", response_model=CourseStats)
    async def get_course_stats():
        try:
            analytics = mock_rag_system.get_course_analytics()
            return CourseStats(
                total_courses=analytics["total_courses"],
                course_titles=analytics["course_titles"]
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.post("/api/clear-session", response_model=ClearSessionResponse)
    async def clear_session(request: ClearSessionRequest):
        try:
            mock_rag_system.session_manager.clear_session(request.session_id)
            return ClearSessionResponse(success=True, message="Session cleared successfully")
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.get("/")
    async def root():
        return {"message": "Course Materials RAG System"}
    
    # Store mock for test access
    app.mock_rag_system = mock_rag_system
    return app


@pytest.fixture
def client(test_app):
    """Create a test client for the FastAPI app"""
    return TestClient(test_app)


@pytest.fixture
def mock_query_response():
    """Mock response data for query endpoint"""
    return {
        "answer": "This is a test answer about machine learning fundamentals.",
        "sources": [
            {
                "course_title": "Test Course",
                "lesson_number": 1,
                "text": "Machine learning is a subset of AI...",
                "link": "https://example.com/lesson1"
            }
        ],
        "session_id": "test-session-123"
    }


@pytest.fixture
def mock_course_analytics():
    """Mock course analytics data"""
    return {
        "total_courses": 3,
        "course_titles": ["Test Course 1", "Test Course 2", "Test Course 3"]
    }