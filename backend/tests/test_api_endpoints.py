"""
Tests for FastAPI endpoints in the RAG system.

This test suite validates:
1. /api/query endpoint - POST requests with query processing
2. /api/courses endpoint - GET requests for course analytics
3. /api/clear-session endpoint - POST requests for session management
4. Root endpoint (/) - GET request for health check
5. Error handling and response validation
6. Request/response schemas and data types
"""

import pytest
from unittest.mock import Mock, patch


@pytest.mark.api
class TestAPIEndpoints:
    """Test suite for FastAPI endpoints"""

    def test_root_endpoint(self, client):
        """Test the root endpoint returns expected message"""
        response = client.get("/")
        
        assert response.status_code == 200
        assert response.json() == {"message": "Course Materials RAG System"}

    def test_query_endpoint_success(self, client, mock_query_response):
        """Test successful query processing through API"""
        # Configure mock to return test data
        mock_rag_system = client.app.mock_rag_system
        mock_rag_system.query.return_value = (
            mock_query_response["answer"],
            mock_query_response["sources"]
        )
        
        # Make API request
        request_data = {"query": "What is machine learning?"}
        response = client.post("/api/query", json=request_data)
        
        # Verify response
        assert response.status_code == 200
        data = response.json()
        
        assert data["answer"] == mock_query_response["answer"]
        assert data["sources"] == mock_query_response["sources"]
        assert "session_id" in data
        assert isinstance(data["session_id"], str)
        
        # Verify mock was called correctly
        mock_rag_system.query.assert_called_once()
        call_args = mock_rag_system.query.call_args
        assert call_args[0][0] == "What is machine learning?"  # query
        assert isinstance(call_args[0][1], str)  # session_id

    def test_query_endpoint_with_session_id(self, client, mock_query_response):
        """Test query endpoint with explicit session ID"""
        # Configure mock
        mock_rag_system = client.app.mock_rag_system
        mock_rag_system.query.return_value = (
            mock_query_response["answer"],
            mock_query_response["sources"]
        )
        
        # Make API request with session ID
        request_data = {
            "query": "Explain neural networks",
            "session_id": "user-session-456"
        }
        response = client.post("/api/query", json=request_data)
        
        # Verify response
        assert response.status_code == 200
        data = response.json()
        
        assert data["session_id"] == "user-session-456"
        
        # Verify mock was called with correct session ID
        mock_rag_system.query.assert_called_once_with(
            "Explain neural networks", 
            "user-session-456"
        )

    def test_query_endpoint_error_handling(self, client):
        """Test query endpoint error handling"""
        # Configure mock to raise exception
        mock_rag_system = client.app.mock_rag_system
        mock_rag_system.query.side_effect = Exception("RAG system error")
        
        # Make API request
        request_data = {"query": "What causes errors?"}
        response = client.post("/api/query", json=request_data)
        
        # Verify error response
        assert response.status_code == 500
        assert response.json()["detail"] == "RAG system error"

    def test_query_endpoint_invalid_request(self, client):
        """Test query endpoint with invalid request data"""
        # Missing required 'query' field
        response = client.post("/api/query", json={})
        
        assert response.status_code == 422  # Validation error

    def test_courses_endpoint_success(self, client, mock_course_analytics):
        """Test successful course analytics retrieval"""
        # Configure mock
        mock_rag_system = client.app.mock_rag_system
        mock_rag_system.get_course_analytics.return_value = mock_course_analytics
        
        # Make API request
        response = client.get("/api/courses")
        
        # Verify response
        assert response.status_code == 200
        data = response.json()
        
        assert data["total_courses"] == mock_course_analytics["total_courses"]
        assert data["course_titles"] == mock_course_analytics["course_titles"]
        
        # Verify mock was called
        mock_rag_system.get_course_analytics.assert_called_once()

    def test_courses_endpoint_error_handling(self, client):
        """Test courses endpoint error handling"""
        # Configure mock to raise exception
        mock_rag_system = client.app.mock_rag_system
        mock_rag_system.get_course_analytics.side_effect = Exception("Analytics error")
        
        # Make API request
        response = client.get("/api/courses")
        
        # Verify error response
        assert response.status_code == 500
        assert response.json()["detail"] == "Analytics error"

    def test_clear_session_endpoint_success(self, client):
        """Test successful session clearing"""
        # Configure mock
        mock_rag_system = client.app.mock_rag_system
        mock_session_manager = Mock()
        mock_rag_system.session_manager = mock_session_manager
        
        # Make API request
        request_data = {"session_id": "session-to-clear"}
        response = client.post("/api/clear-session", json=request_data)
        
        # Verify response
        assert response.status_code == 200
        data = response.json()
        
        assert data["success"] is True
        assert data["message"] == "Session cleared successfully"
        
        # Verify mock was called
        mock_session_manager.clear_session.assert_called_once_with("session-to-clear")

    def test_clear_session_endpoint_error_handling(self, client):
        """Test clear session endpoint error handling"""
        # Configure mock to raise exception
        mock_rag_system = client.app.mock_rag_system
        mock_session_manager = Mock()
        mock_session_manager.clear_session.side_effect = Exception("Session error")
        mock_rag_system.session_manager = mock_session_manager
        
        # Make API request
        request_data = {"session_id": "problematic-session"}
        response = client.post("/api/clear-session", json=request_data)
        
        # Verify error response
        assert response.status_code == 500
        assert response.json()["detail"] == "Session error"

    def test_clear_session_endpoint_invalid_request(self, client):
        """Test clear session endpoint with invalid request data"""
        # Missing required 'session_id' field
        response = client.post("/api/clear-session", json={})
        
        assert response.status_code == 422  # Validation error

    def test_cors_headers(self, client):
        """Test that CORS headers are properly set"""
        response = client.get("/")
        
        # Check for CORS headers (these should be set by the middleware)
        assert response.status_code == 200


@pytest.mark.api
class TestAPIResponseSchemas:
    """Test API response schemas and data validation"""

    def test_query_response_schema(self, client, mock_query_response):
        """Test that query response matches expected schema"""
        mock_rag_system = client.app.mock_rag_system
        mock_rag_system.query.return_value = (
            mock_query_response["answer"],
            mock_query_response["sources"]
        )
        
        request_data = {"query": "Test query"}
        response = client.post("/api/query", json=request_data)
        
        assert response.status_code == 200
        data = response.json()
        
        # Validate response structure
        assert "answer" in data
        assert "sources" in data
        assert "session_id" in data
        
        assert isinstance(data["answer"], str)
        assert isinstance(data["sources"], list)
        assert isinstance(data["session_id"], str)
        
        # Validate sources structure
        if data["sources"]:
            source = data["sources"][0]
            assert isinstance(source, dict)

    def test_courses_response_schema(self, client, mock_course_analytics):
        """Test that courses response matches expected schema"""
        mock_rag_system = client.app.mock_rag_system
        mock_rag_system.get_course_analytics.return_value = mock_course_analytics
        
        response = client.get("/api/courses")
        
        assert response.status_code == 200
        data = response.json()
        
        # Validate response structure
        assert "total_courses" in data
        assert "course_titles" in data
        
        assert isinstance(data["total_courses"], int)
        assert isinstance(data["course_titles"], list)
        
        # Validate course titles are strings
        for title in data["course_titles"]:
            assert isinstance(title, str)

    def test_clear_session_response_schema(self, client):
        """Test that clear session response matches expected schema"""
        mock_rag_system = client.app.mock_rag_system
        mock_rag_system.session_manager = Mock()
        
        request_data = {"session_id": "test-session"}
        response = client.post("/api/clear-session", json=request_data)
        
        assert response.status_code == 200
        data = response.json()
        
        # Validate response structure
        assert "success" in data
        assert "message" in data
        
        assert isinstance(data["success"], bool)
        assert isinstance(data["message"], str)


@pytest.mark.api
class TestAPIIntegration:
    """Integration tests for API endpoint interactions"""

    def test_query_and_clear_session_workflow(self, client, mock_query_response):
        """Test a complete workflow: query -> clear session"""
        mock_rag_system = client.app.mock_rag_system
        mock_rag_system.query.return_value = (
            mock_query_response["answer"],
            mock_query_response["sources"]
        )
        mock_rag_system.session_manager = Mock()
        
        # Step 1: Make a query
        query_request = {"query": "What is AI?"}
        query_response = client.post("/api/query", json=query_request)
        
        assert query_response.status_code == 200
        session_id = query_response.json()["session_id"]
        
        # Step 2: Clear the session
        clear_request = {"session_id": session_id}
        clear_response = client.post("/api/clear-session", json=clear_request)
        
        assert clear_response.status_code == 200
        assert clear_response.json()["success"] is True
        
        # Verify session manager was called
        mock_rag_system.session_manager.clear_session.assert_called_once_with(session_id)

    def test_multiple_queries_same_session(self, client, mock_query_response):
        """Test multiple queries with the same session ID"""
        mock_rag_system = client.app.mock_rag_system
        mock_rag_system.query.return_value = (
            mock_query_response["answer"],
            mock_query_response["sources"]
        )
        
        session_id = "persistent-session"
        
        # Make first query
        request1 = {"query": "First question", "session_id": session_id}
        response1 = client.post("/api/query", json=request1)
        
        assert response1.status_code == 200
        assert response1.json()["session_id"] == session_id
        
        # Make second query with same session
        request2 = {"query": "Second question", "session_id": session_id}
        response2 = client.post("/api/query", json=request2)
        
        assert response2.status_code == 200
        assert response2.json()["session_id"] == session_id
        
        # Verify both calls were made with the same session ID
        assert mock_rag_system.query.call_count == 2
        all_calls = mock_rag_system.query.call_args_list
        assert all_calls[0][0][1] == session_id  # First call session ID
        assert all_calls[1][0][1] == session_id  # Second call session ID