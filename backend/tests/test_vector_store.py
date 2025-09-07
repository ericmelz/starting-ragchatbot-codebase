"""
Tests for VectorStore functionality.

This test suite validates:
1. VectorStore.search() method with different MAX_RESULTS values
2. Impact of MAX_RESULTS=0 on search results
3. Course name resolution and filtering
4. Error handling and edge cases
5. Course outline functionality
"""

import pytest
from unittest.mock import Mock, patch

from vector_store import VectorStore, SearchResults


class TestVectorStore:
    """Test suite for VectorStore core functionality"""

    def test_search_with_proper_max_results(self, populated_vector_store):
        """Test search() with a proper MAX_RESULTS value (5)"""
        results = populated_vector_store.search("testing fundamentals")
        
        # Should return results
        assert not results.is_empty()
        assert results.error is None
        assert len(results.documents) > 0
        assert len(results.metadata) > 0
        assert len(results.documents) == len(results.metadata)

    def test_search_with_zero_max_results(self, temp_chroma_path, sample_course, sample_course_chunks):
        """Test search() with MAX_RESULTS=0 (the broken configuration)"""
        # Create vector store with MAX_RESULTS=0
        broken_store = VectorStore(temp_chroma_path, "all-MiniLM-L6-v2", max_results=0)
        
        # Add test data
        broken_store.add_course_metadata(sample_course)
        broken_store.add_course_content(sample_course_chunks)
        
        # Search should return empty results due to MAX_RESULTS=0
        results = broken_store.search("testing fundamentals")
        
        # Should return empty results with an error (this is the actual bug!)
        assert results.is_empty()
        assert results.error is not None  # ChromaDB throws error for n_results=0
        assert "cannot be negative, or zero" in results.error
        assert len(results.documents) == 0
        assert len(results.metadata) == 0

    def test_search_max_results_comparison(self, temp_chroma_path, sample_course, sample_course_chunks):
        """Compare search results with different MAX_RESULTS values"""
        
        # Create two vector stores with different MAX_RESULTS
        store_with_results = VectorStore(temp_chroma_path + "_good", "all-MiniLM-L6-v2", max_results=5)
        store_zero_results = VectorStore(temp_chroma_path + "_bad", "all-MiniLM-L6-v2", max_results=0)
        
        # Add same data to both
        for store in [store_with_results, store_zero_results]:
            store.add_course_metadata(sample_course)
            store.add_course_content(sample_course_chunks)
        
        query = "testing fundamentals"
        
        # Search both
        good_results = store_with_results.search(query)
        bad_results = store_zero_results.search(query)
        
        # Good store should have results, bad store should be empty
        assert not good_results.is_empty()
        assert bad_results.is_empty()
        
        assert len(good_results.documents) > 0
        assert len(bad_results.documents) == 0

    def test_search_with_course_filtering(self, populated_vector_store):
        """Test search() with course name filtering"""
        
        # Search with existing course
        results = populated_vector_store.search("testing", course_name="Test Course")
        
        if not results.is_empty():
            # All results should be from the specified course
            for metadata in results.metadata:
                assert metadata.get("course_title") == "Test Course"

    def test_search_with_invalid_course_name(self, populated_vector_store):
        """Test search() with non-existent course name"""
        results = populated_vector_store.search("testing", course_name="Nonexistent Course")
        
        # Should return empty results with error about course not found
        assert results.error is not None
        assert "No course found matching" in results.error

    def test_search_with_lesson_filtering(self, populated_vector_store):
        """Test search() with lesson number filtering"""
        results = populated_vector_store.search("testing", lesson_number=1)
        
        if not results.is_empty():
            # All results should be from lesson 1
            for metadata in results.metadata:
                assert metadata.get("lesson_number") == 1

    def test_search_with_combined_filters(self, populated_vector_store):
        """Test search() with both course and lesson filters"""
        results = populated_vector_store.search(
            "testing", 
            course_name="Test Course", 
            lesson_number=2
        )
        
        if not results.is_empty():
            # All results should match both filters
            for metadata in results.metadata:
                assert metadata.get("course_title") == "Test Course"
                assert metadata.get("lesson_number") == 2

    def test_search_with_custom_limit(self, populated_vector_store):
        """Test search() with custom limit parameter"""
        # Test with custom limit that overrides MAX_RESULTS
        results = populated_vector_store.search("testing", limit=2)
        
        if not results.is_empty():
            # Should respect custom limit
            assert len(results.documents) <= 2

    def test_search_with_zero_custom_limit(self, populated_vector_store):
        """Test search() with custom limit=0"""
        results = populated_vector_store.search("testing", limit=0)
        
        # Should return empty results when explicitly set to 0
        assert results.is_empty()

    def test_course_name_resolution(self, populated_vector_store):
        """Test _resolve_course_name() method"""
        
        # Test exact match
        resolved = populated_vector_store._resolve_course_name("Test Course")
        assert resolved == "Test Course"
        
        # Test partial match (should work with semantic search)
        resolved = populated_vector_store._resolve_course_name("Test")
        assert resolved == "Test Course"  # Should find the best match
        
        # Test non-existent course
        resolved = populated_vector_store._resolve_course_name("Completely Invalid Course")
        assert resolved is None

    def test_build_filter_logic(self, test_vector_store):
        """Test _build_filter() method with various combinations"""
        
        # No filters
        filter_dict = test_vector_store._build_filter(None, None)
        assert filter_dict is None
        
        # Course only
        filter_dict = test_vector_store._build_filter("Test Course", None)
        assert filter_dict == {"course_title": "Test Course"}
        
        # Lesson only
        filter_dict = test_vector_store._build_filter(None, 1)
        assert filter_dict == {"lesson_number": 1}
        
        # Both filters
        filter_dict = test_vector_store._build_filter("Test Course", 1)
        expected = {"$and": [
            {"course_title": "Test Course"},
            {"lesson_number": 1}
        ]}
        assert filter_dict == expected

    def test_get_course_outline(self, populated_vector_store):
        """Test get_course_outline() method"""
        outline = populated_vector_store.get_course_outline("Test Course")
        
        assert outline is not None
        assert outline["course_title"] == "Test Course"
        assert outline["instructor"] == "Test Instructor"
        assert outline["course_link"] == "https://example.com/course"
        assert "lessons" in outline
        assert len(outline["lessons"]) == 3

    def test_get_course_outline_with_partial_name(self, populated_vector_store):
        """Test get_course_outline() with partial course name"""
        outline = populated_vector_store.get_course_outline("Test")
        
        assert outline is not None
        assert outline["course_title"] == "Test Course"

    def test_get_course_outline_nonexistent(self, populated_vector_store):
        """Test get_course_outline() with non-existent course"""
        outline = populated_vector_store.get_course_outline("Nonexistent Course")
        
        assert outline is None

    def test_get_lesson_link(self, populated_vector_store):
        """Test get_lesson_link() method"""
        link = populated_vector_store.get_lesson_link("Test Course", 1)
        
        assert link == "https://example.com/lesson1"

    def test_get_lesson_link_invalid(self, populated_vector_store):
        """Test get_lesson_link() with invalid parameters"""
        
        # Invalid course
        link = populated_vector_store.get_lesson_link("Invalid Course", 1)
        assert link is None
        
        # Invalid lesson number
        link = populated_vector_store.get_lesson_link("Test Course", 999)
        assert link is None


class TestVectorStoreConfiguration:
    """Test vector store behavior with different configurations"""

    def test_initialization_with_different_max_results(self, temp_chroma_path):
        """Test VectorStore initialization with different MAX_RESULTS values"""
        
        # Test with normal value
        store_normal = VectorStore(temp_chroma_path + "_normal", "all-MiniLM-L6-v2", max_results=5)
        assert store_normal.max_results == 5
        
        # Test with zero (the problematic value)
        store_zero = VectorStore(temp_chroma_path + "_zero", "all-MiniLM-L6-v2", max_results=0)
        assert store_zero.max_results == 0
        
        # Test with large value
        store_large = VectorStore(temp_chroma_path + "_large", "all-MiniLM-L6-v2", max_results=100)
        assert store_large.max_results == 100


class TestSearchResults:
    """Test SearchResults data class functionality"""

    def test_search_results_from_chroma(self):
        """Test SearchResults.from_chroma() class method"""
        
        # Mock ChromaDB results
        chroma_results = {
            'documents': [['doc1', 'doc2']],
            'metadatas': [[{'course': 'test1'}, {'course': 'test2'}]],
            'distances': [[0.1, 0.2]]
        }
        
        results = SearchResults.from_chroma(chroma_results)
        
        assert results.documents == ['doc1', 'doc2']
        assert results.metadata == [{'course': 'test1'}, {'course': 'test2'}]
        assert results.distances == [0.1, 0.2]
        assert results.error is None

    def test_search_results_empty(self):
        """Test SearchResults.empty() class method"""
        error_msg = "Test error message"
        results = SearchResults.empty(error_msg)
        
        assert results.documents == []
        assert results.metadata == []
        assert results.distances == []
        assert results.error == error_msg
        assert results.is_empty()

    def test_search_results_is_empty(self):
        """Test SearchResults.is_empty() method"""
        
        # Empty results
        empty_results = SearchResults([], [], [])
        assert empty_results.is_empty()
        
        # Non-empty results  
        non_empty_results = SearchResults(['doc'], [{'meta': 'data'}], [0.1])
        assert not non_empty_results.is_empty()


class TestVectorStoreErrorHandling:
    """Test error handling in VectorStore operations"""

    def test_search_with_chroma_exception(self, populated_vector_store):
        """Test search() when ChromaDB raises an exception"""
        
        with patch.object(populated_vector_store.course_content, 'query') as mock_query:
            mock_query.side_effect = Exception("ChromaDB connection error")
            
            results = populated_vector_store.search("test query")
            
            assert results.error is not None
            assert "Search error" in results.error
            assert "ChromaDB connection error" in results.error

    def test_course_name_resolution_exception(self, populated_vector_store):
        """Test _resolve_course_name() when ChromaDB raises an exception"""
        
        with patch.object(populated_vector_store.course_catalog, 'query') as mock_query:
            mock_query.side_effect = Exception("Connection failed")
            
            resolved = populated_vector_store._resolve_course_name("Test Course")
            
            # Should return None when resolution fails
            assert resolved is None

    def test_get_course_outline_exception(self, populated_vector_store):
        """Test get_course_outline() when ChromaDB raises an exception"""
        
        with patch.object(populated_vector_store.course_catalog, 'get') as mock_get:
            mock_get.side_effect = Exception("Database error")
            
            outline = populated_vector_store.get_course_outline("Test Course")
            
            # Should return None when operation fails
            assert outline is None