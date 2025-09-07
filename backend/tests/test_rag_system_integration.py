"""
Integration tests for RAG System.

This test suite validates:
1. Full query flow from end-to-end
2. Different query types (content vs outline vs general)
3. Tool registration and management
4. Error propagation through the system
5. Integration between all components
"""

from unittest.mock import MagicMock, Mock, patch

import pytest
from rag_system import RAGSystem
from search_tools import ToolManager


class TestRAGSystemInitialization:
    """Test RAG system initialization and component setup"""

    def test_rag_system_initialization(self, test_config):
        """Test RAGSystem properly initializes all components"""
        with (
            patch("rag_system.VectorStore") as mock_vs,
            patch("rag_system.AIGenerator") as mock_ai,
            patch("rag_system.DocumentProcessor") as mock_dp,
            patch("rag_system.SessionManager") as mock_sm,
        ):

            rag = RAGSystem(test_config)

            # Should initialize all components
            mock_vs.assert_called_once()
            mock_ai.assert_called_once()
            mock_dp.assert_called_once()
            mock_sm.assert_called_once()

            # Should have tool manager with registered tools
            assert isinstance(rag.tool_manager, ToolManager)

            # Should have both tools registered
            tool_definitions = rag.tool_manager.get_tool_definitions()
            tool_names = [tool["name"] for tool in tool_definitions]
            assert "search_course_content" in tool_names
            assert "get_course_outline" in tool_names

    def test_rag_system_config_propagation(self, test_config):
        """Test that config values are properly propagated to components"""
        with (
            patch("rag_system.VectorStore") as mock_vs,
            patch("rag_system.AIGenerator") as mock_ai,
            patch("rag_system.DocumentProcessor") as mock_dp,
            patch("rag_system.SessionManager") as mock_sm,
        ):

            rag = RAGSystem(test_config)

            # Check VectorStore initialization
            mock_vs.assert_called_once_with(
                test_config.CHROMA_PATH,
                test_config.EMBEDDING_MODEL,
                test_config.MAX_RESULTS,
            )

            # Check AIGenerator initialization
            mock_ai.assert_called_once_with(
                test_config.ANTHROPIC_API_KEY, test_config.ANTHROPIC_MODEL
            )

            # Check DocumentProcessor initialization
            mock_dp.assert_called_once_with(
                test_config.CHUNK_SIZE, test_config.CHUNK_OVERLAP
            )

            # Check SessionManager initialization
            mock_sm.assert_called_once_with(test_config.MAX_HISTORY)

    def test_rag_system_with_broken_config(self, broken_config):
        """Test RAG system initialization with broken MAX_RESULTS=0 config"""
        with patch("rag_system.VectorStore") as mock_vs:
            rag = RAGSystem(broken_config)

            # Should still initialize, but with broken MAX_RESULTS
            mock_vs.assert_called_once_with(
                broken_config.CHROMA_PATH,
                broken_config.EMBEDDING_MODEL,
                0,  # This is the broken value
            )


class TestRAGSystemQueryFlow:
    """Test the complete query flow through the RAG system"""

    def test_query_without_session(self, rag_system):
        """Test query() without providing session_id"""
        rag = rag_system

        # Mock the AI generator response
        rag.mock_ai_generator.generate_response.return_value = "Test response"

        # Mock session manager to create session
        rag.session_manager.create_session.return_value = "new_session_123"

        response, sources = rag.query("What is machine learning?")

        # Should create new session
        rag.session_manager.create_session.assert_called_once()

        # Should call AI generator with tools
        rag.mock_ai_generator.generate_response.assert_called_once()
        call_args = rag.mock_ai_generator.generate_response.call_args

        # Verify query format
        assert "Answer this question about course materials:" in call_args[0][0]
        assert "What is machine learning?" in call_args[0][0]

        # Should include tools
        assert call_args[1]["tools"] is not None
        assert call_args[1]["tool_manager"] is not None

    def test_query_with_existing_session(self, rag_system):
        """Test query() with existing session_id"""
        rag = rag_system

        # Mock session history
        rag.session_manager.get_conversation_history.return_value = (
            "Previous conversation..."
        )
        rag.mock_ai_generator.generate_response.return_value = "Test response"

        response, sources = rag.query(
            "Follow up question", session_id="existing_session"
        )

        # Should get conversation history
        rag.session_manager.get_conversation_history.assert_called_once_with(
            "existing_session"
        )

        # Should pass history to AI generator
        call_args = rag.mock_ai_generator.generate_response.call_args
        assert call_args[1]["conversation_history"] == "Previous conversation..."

    def test_query_source_tracking(self, rag_system):
        """Test that sources are properly tracked and returned"""
        rag = rag_system

        # Mock AI response
        rag.mock_ai_generator.generate_response.return_value = "Test response"

        # Mock tool manager to return sources
        test_sources = [
            {"text": "Test Course - Lesson 1", "link": "https://example.com/lesson1"},
            {"text": "Another Course", "link": None},
        ]
        rag.tool_manager.get_last_sources = Mock(return_value=test_sources)
        rag.tool_manager.reset_sources = Mock()

        response, sources = rag.query("Test query")

        # Should get and reset sources
        rag.tool_manager.get_last_sources.assert_called_once()
        rag.tool_manager.reset_sources.assert_called_once()

        # Should return the sources
        assert sources == test_sources

    def test_query_session_update(self, rag_system):
        """Test that conversation history is updated after query"""
        rag = rag_system

        query_text = "What is testing?"
        ai_response = "Testing is the process..."
        session_id = "test_session"

        rag.mock_ai_generator.generate_response.return_value = ai_response

        response, sources = rag.query(query_text, session_id=session_id)

        # Should update conversation history
        rag.session_manager.add_exchange.assert_called_once_with(
            session_id, query_text, ai_response
        )


class TestRAGSystemErrorHandling:
    """Test error handling throughout the RAG system"""

    def test_query_ai_generator_exception(self, rag_system):
        """Test query() when AI generator raises exception"""
        rag = rag_system

        # Mock AI generator to raise exception
        rag.mock_ai_generator.generate_response.side_effect = Exception("API error")

        # Should propagate exception
        with pytest.raises(Exception) as exc_info:
            rag.query("Test query")

        assert "API error" in str(exc_info.value)

    def test_query_tool_manager_error(self, rag_system):
        """Test query() when tool manager has issues"""
        rag = rag_system

        # Mock AI generator to return response
        rag.mock_ai_generator.generate_response.return_value = "Response"

        # Mock tool manager to raise exception when getting sources
        rag.tool_manager.get_last_sources = Mock(side_effect=Exception("Tool error"))

        # Should handle gracefully and still return response
        response, sources = rag.query("Test query")

        assert response == "Response"
        # Sources might be empty or None depending on error handling

    def test_query_session_manager_error(self, rag_system):
        """Test query() when session manager has issues"""
        rag = rag_system

        # Mock session manager methods to raise exceptions
        rag.session_manager.get_conversation_history.side_effect = Exception(
            "Session error"
        )
        rag.mock_ai_generator.generate_response.return_value = "Response"

        # Should still work (might not use history)
        response, sources = rag.query("Test query", session_id="test")

        assert response == "Response"


class TestRAGSystemToolIntegration:
    """Test integration between RAG system and tools"""

    def test_tool_definitions_passed_to_ai(self, rag_system):
        """Test that tool definitions are properly passed to AI generator"""
        rag = rag_system

        rag.mock_ai_generator.generate_response.return_value = "Test response"

        rag.query("Test query")

        call_args = rag.mock_ai_generator.generate_response.call_args
        tools = call_args[1]["tools"]

        # Should be a list of tool definitions
        assert isinstance(tools, list)
        assert len(tools) >= 2  # At least search and outline tools

        # Each tool should have required structure
        for tool in tools:
            assert "name" in tool
            assert "description" in tool
            assert "input_schema" in tool

    def test_tool_manager_passed_to_ai(self, rag_system):
        """Test that tool manager is passed to AI generator"""
        rag = rag_system

        rag.mock_ai_generator.generate_response.return_value = "Test response"

        rag.query("Test query")

        call_args = rag.mock_ai_generator.generate_response.call_args
        tool_manager = call_args[1]["tool_manager"]

        # Should pass the actual tool manager instance
        assert tool_manager is rag.tool_manager

    def test_different_query_types_handling(self, rag_system):
        """Test that different query types are handled appropriately"""
        rag = rag_system

        # Mock different AI responses for different query types
        rag.mock_ai_generator.generate_response.return_value = "Response"

        # Test content query
        response1, _ = rag.query("What is covered in lesson 1?")

        # Test outline query
        response2, _ = rag.query("What is the outline of the course?")

        # Test general query
        response3, _ = rag.query("What is machine learning?")

        # All should complete successfully
        assert response1 == "Response"
        assert response2 == "Response"
        assert response3 == "Response"

        # Should make 3 separate AI calls
        assert rag.mock_ai_generator.generate_response.call_count == 3


class TestRAGSystemCourseManagement:
    """Test course document management functionality"""

    def test_add_course_document(self, rag_system, sample_course):
        """Test add_course_document() functionality"""
        rag = rag_system

        # Mock document processor
        rag.document_processor.process_course_document.return_value = (
            sample_course,
            [],
        )

        with patch("os.path.exists") as mock_exists:
            mock_exists.return_value = True

            course, chunk_count = rag.add_course_document("/fake/path/course.txt")

            # Should process document
            rag.document_processor.process_course_document.assert_called_once_with(
                "/fake/path/course.txt"
            )

            # Should add to vector store
            rag.mock_vector_store.add_course_metadata.assert_called_once_with(
                sample_course
            )
            rag.mock_vector_store.add_course_content.assert_called_once_with([])

    def test_add_course_folder(self, rag_system):
        """Test add_course_folder() functionality"""
        rag = rag_system

        # Mock filesystem operations
        with (
            patch("os.path.exists") as mock_exists,
            patch("os.listdir") as mock_listdir,
        ):

            mock_exists.return_value = True
            mock_listdir.return_value = [
                "course1.txt",
                "course2.txt",
                "not_a_course.jpg",
            ]

            # Mock existing courses
            rag.mock_vector_store.get_existing_course_titles.return_value = []

            courses, chunks = rag.add_course_folder("/fake/docs")

            # Should check existing courses
            rag.mock_vector_store.get_existing_course_titles.assert_called_once()

    def test_get_course_analytics(self, rag_system):
        """Test get_course_analytics() functionality"""
        rag = rag_system

        # Mock vector store analytics
        rag.mock_vector_store.get_course_count.return_value = 5
        rag.mock_vector_store.get_existing_course_titles.return_value = [
            "Course 1",
            "Course 2",
            "Course 3",
            "Course 4",
            "Course 5",
        ]

        analytics = rag.get_course_analytics()

        assert analytics["total_courses"] == 5
        assert len(analytics["course_titles"]) == 5
        assert "Course 1" in analytics["course_titles"]


class TestRAGSystemWithRealComponents:
    """Integration tests with actual (non-mocked) components where safe"""

    def test_tool_manager_real_registration(self, test_config, temp_chroma_path):
        """Test that tools are actually registered correctly"""
        test_config.CHROMA_PATH = temp_chroma_path

        # Use real components for tool registration (safe to test)
        with (
            patch("rag_system.AIGenerator") as mock_ai,
            patch("rag_system.DocumentProcessor") as mock_dp,
            patch("rag_system.SessionManager") as mock_sm,
        ):

            rag = RAGSystem(test_config)

            # Tool manager should be real
            assert isinstance(rag.tool_manager, ToolManager)

            # Should have real tools registered
            tools = rag.tool_manager.get_tool_definitions()
            assert len(tools) == 2

            tool_names = [tool["name"] for tool in tools]
            assert "search_course_content" in tool_names
            assert "get_course_outline" in tool_names

            # Tool definitions should be properly structured
            for tool in tools:
                assert "name" in tool
                assert "description" in tool
                assert "input_schema" in tool
                assert "properties" in tool["input_schema"]
                assert "required" in tool["input_schema"]

    def test_session_creation_flow(self, test_config, temp_chroma_path):
        """Test session creation in query flow"""
        test_config.CHROMA_PATH = temp_chroma_path

        with (
            patch("rag_system.AIGenerator") as mock_ai,
            patch("rag_system.VectorStore") as mock_vs,
            patch("rag_system.DocumentProcessor") as mock_dp,
        ):

            # Mock AI generator response
            mock_ai_instance = Mock()
            mock_ai_instance.generate_response.return_value = "Test response"
            mock_ai.return_value = mock_ai_instance

            rag = RAGSystem(test_config)

            # Query without session should create one
            response, sources = rag.query("Test query")

            # Should have created and used a session
            assert len(response) > 0
            # Session manager should be real and working
            sessions = rag.session_manager.sessions
            assert len(sessions) >= 1  # At least one session created
