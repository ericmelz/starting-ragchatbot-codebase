"""
Tests for CourseSearchTool functionality.

This test suite validates:
1. CourseSearchTool.execute() method behavior
2. Impact of MAX_RESULTS=0 vs proper values
3. Course name filtering and lesson filtering
4. Source tracking and result formatting
5. Error handling for various scenarios
"""

import pytest
from unittest.mock import Mock, patch

from search_tools import CourseSearchTool
from vector_store import SearchResults


class TestCourseSearchTool:
    """Test suite for CourseSearchTool functionality"""

    def test_tool_definition_structure(self, course_search_tool):
        """Test that tool definition is properly structured for Anthropic API"""
        tool_def = course_search_tool.get_tool_definition()
        
        # Verify required structure
        assert "name" in tool_def
        assert "description" in tool_def
        assert "input_schema" in tool_def
        
        # Verify specific values
        assert tool_def["name"] == "search_course_content"
        assert "Search course materials" in tool_def["description"]
        
        # Verify schema structure
        schema = tool_def["input_schema"]
        assert schema["type"] == "object"
        assert "properties" in schema
        assert "required" in schema
        
        # Verify required and optional parameters
        properties = schema["properties"]
        assert "query" in properties
        assert "course_name" in properties
        assert "lesson_number" in properties
        
        assert schema["required"] == ["query"]

    def test_execute_with_valid_query_working_config(self, course_search_tool):
        """Test execute() with a valid query using working MAX_RESULTS config"""
        result = course_search_tool.execute("testing basics")
        
        # Should find content and return formatted results
        assert result is not None
        assert isinstance(result, str)
        assert len(result) > 0
        
        # Should not be an error message
        assert not result.startswith("No relevant content found")
        
        # Should contain course context in brackets
        assert "[Test Course" in result
        
        # Should track sources
        assert len(course_search_tool.last_sources) > 0

    def test_execute_with_broken_max_results(self, broken_course_search_tool):
        """Test execute() with MAX_RESULTS=0 (the broken configuration)"""
        result = broken_course_search_tool.execute("testing basics")
        
        # With MAX_RESULTS=0, should return ChromaDB error
        assert result.startswith("Search error:")
        assert "cannot be negative, or zero" in result
        
        # Should not track any sources since search failed with error
        assert len(broken_course_search_tool.last_sources) == 0

    def test_execute_with_course_filtering(self, course_search_tool):
        """Test execute() with course name filtering"""
        # Test with exact course name
        result = course_search_tool.execute("testing", course_name="Test Course")
        assert result is not None
        assert "[Test Course" in result
        
        # Test with non-existent course
        result = course_search_tool.execute("testing", course_name="Nonexistent Course")
        assert "No course found matching 'Nonexistent Course'" in result

    def test_execute_with_lesson_filtering(self, course_search_tool):
        """Test execute() with lesson number filtering"""
        # Test with specific lesson
        result = course_search_tool.execute("testing", lesson_number=1)
        assert result is not None
        
        # Should contain lesson context
        if not result.startswith("No relevant content found"):
            assert "Lesson 1" in result

    def test_execute_with_combined_filtering(self, course_search_tool):
        """Test execute() with both course and lesson filtering"""
        result = course_search_tool.execute(
            "testing", 
            course_name="Test Course", 
            lesson_number=2
        )
        assert result is not None
        
        # Should work with combined filters if content exists
        if not result.startswith("No relevant content found"):
            assert "[Test Course - Lesson 2]" in result

    def test_execute_with_invalid_inputs(self, course_search_tool):
        """Test execute() with various invalid inputs"""
        
        # Empty query
        result = course_search_tool.execute("")
        # Should still work, might just return no results or general content
        assert isinstance(result, str)
        
        # Invalid lesson number
        result = course_search_tool.execute("testing", lesson_number=999)
        # Should handle gracefully - might return no results
        assert isinstance(result, str)

    def test_format_results_with_sources(self, course_search_tool):
        """Test _format_results() method with source tracking"""
        # Create mock search results
        mock_results = SearchResults(
            documents=["Content from lesson 1", "Content from lesson 2"],
            metadata=[
                {"course_title": "Test Course", "lesson_number": 1},
                {"course_title": "Test Course", "lesson_number": 2}
            ],
            distances=[0.1, 0.2]
        )
        
        formatted = course_search_tool._format_results(mock_results)
        
        # Check formatting
        assert "[Test Course - Lesson 1]" in formatted
        assert "[Test Course - Lesson 2]" in formatted
        assert "Content from lesson 1" in formatted
        assert "Content from lesson 2" in formatted
        
        # Check source tracking
        assert len(course_search_tool.last_sources) == 2
        
        # Verify source structure
        for source in course_search_tool.last_sources:
            assert isinstance(source, dict)
            assert "text" in source
            assert "link" in source  # May be None

    def test_format_results_with_links(self, course_search_tool):
        """Test _format_results() creates proper source links"""
        # Mock the get_lesson_link method to return a test link
        with patch.object(course_search_tool.store, 'get_lesson_link') as mock_get_link:
            mock_get_link.return_value = "https://example.com/lesson1"
            
            mock_results = SearchResults(
                documents=["Test content"],
                metadata=[{"course_title": "Test Course", "lesson_number": 1}],
                distances=[0.1]
            )
            
            course_search_tool._format_results(mock_results)
            
            # Should have called get_lesson_link
            mock_get_link.assert_called_once_with("Test Course", 1)
            
            # Should track source with link
            assert len(course_search_tool.last_sources) == 1
            source = course_search_tool.last_sources[0]
            assert source["text"] == "Test Course - Lesson 1"
            assert source["link"] == "https://example.com/lesson1"

    def test_format_results_without_lesson_number(self, course_search_tool):
        """Test _format_results() with metadata missing lesson_number"""
        mock_results = SearchResults(
            documents=["General course content"],
            metadata=[{"course_title": "Test Course"}],  # No lesson_number
            distances=[0.1]
        )
        
        formatted = course_search_tool._format_results(mock_results)
        
        # Should handle missing lesson number gracefully
        assert "[Test Course]" in formatted  # No lesson number in header
        assert "General course content" in formatted
        
        # Source should not have lesson number
        assert len(course_search_tool.last_sources) == 1
        source = course_search_tool.last_sources[0]
        assert source["text"] == "Test Course"
        assert source["link"] is None  # No lesson link without lesson number

    def test_source_tracking_reset(self, course_search_tool):
        """Test that sources are properly tracked and can be reset"""
        # Execute a query to populate sources
        course_search_tool.execute("testing")
        initial_sources = len(course_search_tool.last_sources)
        
        # Execute another query - should replace sources
        course_search_tool.execute("advanced")
        
        # Sources should be updated (might be same count, but different content)
        assert isinstance(course_search_tool.last_sources, list)
        
        # Manual reset
        course_search_tool.last_sources = []
        assert len(course_search_tool.last_sources) == 0

    def test_error_handling_in_vector_store(self, test_vector_store):
        """Test CourseSearchTool handles vector store errors gracefully"""
        search_tool = CourseSearchTool(test_vector_store)
        
        # Mock vector store to raise exception
        with patch.object(test_vector_store, 'search') as mock_search:
            mock_search.return_value = SearchResults.empty("Search error: Connection failed")
            
            result = search_tool.execute("test query")
            
            # Should return the error message
            assert result == "Search error: Connection failed"

    def test_course_name_resolution_failure(self, course_search_tool):
        """Test behavior when course name cannot be resolved"""
        result = course_search_tool.execute("test", course_name="Totally Invalid Course Name")
        
        # Should return specific error about course not found
        assert "No course found matching" in result
        assert "Totally Invalid Course Name" in result

    def test_multiple_queries_source_isolation(self, course_search_tool):
        """Test that sources from different queries don't interfere"""
        # First query
        result1 = course_search_tool.execute("testing basics")
        sources1 = course_search_tool.last_sources.copy()
        
        # Second query with different parameters  
        result2 = course_search_tool.execute("advanced concepts", lesson_number=2)
        sources2 = course_search_tool.last_sources.copy()
        
        # Sources should be different (unless identical results)
        # At minimum, the source tracking should be working independently
        assert isinstance(sources1, list)
        assert isinstance(sources2, list)
        
        # The current sources should be from the most recent query
        assert course_search_tool.last_sources == sources2


class TestCourseSearchToolComparison:
    """Compare behavior between working and broken configurations"""
    
    def test_same_query_different_configs(self, course_search_tool, broken_course_search_tool):
        """Test identical query with working vs broken MAX_RESULTS config"""
        query = "testing fundamentals"
        
        # Working config should return content
        working_result = course_search_tool.execute(query)
        
        # Broken config should return "No relevant content found"
        broken_result = broken_course_search_tool.execute(query)
        
        # Results should be different
        assert working_result != broken_result
        
        # Working should have content, broken should show ChromaDB error
        assert not working_result.startswith("No relevant content found")
        assert not working_result.startswith("Search error:")
        assert broken_result.startswith("Search error:")
        assert "cannot be negative, or zero" in broken_result
        
        # Working should have sources, broken should not
        assert len(course_search_tool.last_sources) > 0
        assert len(broken_course_search_tool.last_sources) == 0

    def test_source_tracking_comparison(self, course_search_tool, broken_course_search_tool):
        """Compare source tracking between configs"""
        query = "integration testing"
        
        # Execute same query on both
        course_search_tool.execute(query)
        broken_course_search_tool.execute(query)
        
        # Working config should track sources
        working_sources = course_search_tool.last_sources
        broken_sources = broken_course_search_tool.last_sources
        
        assert len(working_sources) > 0
        assert len(broken_sources) == 0
        
        # Verify working sources have proper structure
        for source in working_sources:
            assert "text" in source
            assert "link" in source