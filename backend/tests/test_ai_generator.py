"""
Tests for AIGenerator functionality.

This test suite validates:
1. Tool definition handling and validation
2. Tool calling mechanism with Anthropic API
3. Response generation with and without tools
4. Error handling in tool execution
5. System prompt behavior and tool usage
"""

import pytest
from unittest.mock import Mock, patch, MagicMock

from ai_generator import AIGenerator


class TestAIGeneratorBasics:
    """Test basic AIGenerator functionality"""

    def test_initialization(self, test_config):
        """Test AIGenerator initialization"""
        ai_gen = AIGenerator(test_config.ANTHROPIC_API_KEY, test_config.ANTHROPIC_MODEL)
        
        assert ai_gen.model == test_config.ANTHROPIC_MODEL
        assert ai_gen.base_params["model"] == test_config.ANTHROPIC_MODEL
        assert ai_gen.base_params["temperature"] == 0
        assert ai_gen.base_params["max_tokens"] == 800

    def test_system_prompt_structure(self):
        """Test that system prompt contains required elements"""
        system_prompt = AIGenerator.SYSTEM_PROMPT
        
        # Should mention both tools
        assert "get_course_outline" in system_prompt
        assert "search_course_content" in system_prompt
        
        # Should have clear usage guidelines
        assert "Course outline/structure questions" in system_prompt
        assert "Content-specific questions" in system_prompt
        
        # Should have response protocol
        assert "General knowledge questions" in system_prompt
        assert "No meta-commentary" in system_prompt

    def test_generate_response_without_tools(self, ai_generator_with_mock):
        """Test generate_response() without any tools"""
        ai_gen = ai_generator_with_mock
        
        response = ai_gen.generate_response("What is machine learning?")
        
        # Should call Anthropic API
        ai_gen.client.messages.create.assert_called_once()
        
        # Should return text response
        assert response == "Test AI response"
        
        # Verify call parameters
        call_args = ai_gen.client.messages.create.call_args
        assert call_args[1]["model"] == ai_gen.model
        assert call_args[1]["temperature"] == 0
        assert call_args[1]["max_tokens"] == 800
        assert "tools" not in call_args[1]

    def test_generate_response_with_conversation_history(self, ai_generator_with_mock):
        """Test generate_response() with conversation history"""
        ai_gen = ai_generator_with_mock
        
        history = "User: Hello\nAssistant: Hi there!"
        response = ai_gen.generate_response("What's next?", conversation_history=history)
        
        # Should include history in system prompt
        call_args = ai_gen.client.messages.create.call_args
        system_content = call_args[1]["system"]
        assert "Previous conversation:" in system_content
        assert history in system_content


class TestAIGeneratorToolCalling:
    """Test AIGenerator tool calling functionality"""

    def test_generate_response_with_tools(self, ai_generator_with_mock, tool_manager):
        """Test generate_response() with tools available"""
        ai_gen = ai_generator_with_mock
        
        # Mock response that doesn't use tools (stop_reason != "tool_use")
        ai_gen.client.messages.create.return_value.stop_reason = "end_turn"
        
        tools = tool_manager.get_tool_definitions()
        response = ai_gen.generate_response(
            "What is machine learning?", 
            tools=tools, 
            tool_manager=tool_manager
        )
        
        # Should include tools in API call
        call_args = ai_gen.client.messages.create.call_args
        assert "tools" in call_args[1]
        assert "tool_choice" in call_args[1]
        assert call_args[1]["tool_choice"] == {"type": "auto"}
        
        # Should have both tools
        passed_tools = call_args[1]["tools"]
        tool_names = [tool["name"] for tool in passed_tools]
        assert "search_course_content" in tool_names
        assert "get_course_outline" in tool_names

    def test_tool_execution_flow(self, ai_generator_with_mock, tool_manager):
        """Test the complete tool execution flow"""
        ai_gen = ai_generator_with_mock
        
        # Mock initial response that requests tool use
        initial_response = Mock()
        initial_response.stop_reason = "tool_use"
        initial_response.content = [Mock()]
        initial_response.content[0].type = "tool_use"
        initial_response.content[0].name = "search_course_content"
        initial_response.content[0].input = {"query": "test query"}
        initial_response.content[0].id = "tool_call_123"
        
        # Mock final response after tool execution
        final_response = Mock()
        final_response.content = [Mock()]
        final_response.content[0].text = "Here's what I found about testing..."
        
        # Set up mock to return different responses on subsequent calls
        ai_gen.client.messages.create.side_effect = [initial_response, final_response]
        
        # Mock tool manager to return a result
        with patch.object(tool_manager, 'execute_tool') as mock_execute:
            mock_execute.return_value = "Tool execution result"
            
            tools = tool_manager.get_tool_definitions()
            response = ai_gen.generate_response(
                "What is testing?",
                tools=tools,
                tool_manager=tool_manager
            )
            
            # Should execute the tool
            mock_execute.assert_called_once_with(
                "search_course_content",
                query="test query"
            )
            
            # Should return final response
            assert response == "Here's what I found about testing..."
            
            # Should make two API calls (initial + follow-up)
            assert ai_gen.client.messages.create.call_count == 2

    def test_multiple_tool_calls_in_response(self, ai_generator_with_mock, tool_manager):
        """Test handling multiple tool calls in a single response"""
        ai_gen = ai_generator_with_mock
        
        # Mock response with multiple tool calls
        initial_response = Mock()
        initial_response.stop_reason = "tool_use"
        initial_response.content = [Mock(), Mock()]
        
        # First tool call
        initial_response.content[0].type = "tool_use"
        initial_response.content[0].name = "search_course_content"
        initial_response.content[0].input = {"query": "test1"}
        initial_response.content[0].id = "call_1"
        
        # Second tool call
        initial_response.content[1].type = "tool_use"
        initial_response.content[1].name = "get_course_outline"
        initial_response.content[1].input = {"course_name": "Test Course"}
        initial_response.content[1].id = "call_2"
        
        # Mock final response
        final_response = Mock()
        final_response.content = [Mock()]
        final_response.content[0].text = "Combined results"
        
        ai_gen.client.messages.create.side_effect = [initial_response, final_response]
        
        with patch.object(tool_manager, 'execute_tool') as mock_execute:
            mock_execute.return_value = "Tool result"
            
            tools = tool_manager.get_tool_definitions()
            response = ai_gen.generate_response(
                "Tell me about the course",
                tools=tools,
                tool_manager=tool_manager
            )
            
            # Should execute both tools
            assert mock_execute.call_count == 2
            mock_execute.assert_any_call("search_course_content", query="test1")
            mock_execute.assert_any_call("get_course_outline", course_name="Test Course")

    def test_tool_execution_error_handling(self, ai_generator_with_mock, tool_manager):
        """Test error handling during tool execution"""
        ai_gen = ai_generator_with_mock
        
        # Mock response that requests tool use
        initial_response = Mock()
        initial_response.stop_reason = "tool_use"
        initial_response.content = [Mock()]
        initial_response.content[0].type = "tool_use"
        initial_response.content[0].name = "search_course_content"
        initial_response.content[0].input = {"query": "test"}
        initial_response.content[0].id = "tool_call_123"
        
        # Mock final response
        final_response = Mock()
        final_response.content = [Mock()]
        final_response.content[0].text = "Error occurred"
        
        ai_gen.client.messages.create.side_effect = [initial_response, final_response]
        
        # Mock tool manager to return an error
        with patch.object(tool_manager, 'execute_tool') as mock_execute:
            mock_execute.return_value = "Tool 'search_course_content' not found"
            
            tools = tool_manager.get_tool_definitions()
            response = ai_gen.generate_response(
                "Search for something",
                tools=tools,
                tool_manager=tool_manager
            )
            
            # Should still complete and return response
            assert response == "Error occurred"


class TestAIGeneratorMessageFlow:
    """Test message construction and flow in AIGenerator"""

    def test_message_construction_basic(self, ai_generator_with_mock):
        """Test basic message construction"""
        ai_gen = ai_generator_with_mock
        
        ai_gen.generate_response("Test query")
        
        call_args = ai_gen.client.messages.create.call_args
        messages = call_args[1]["messages"]
        
        assert len(messages) == 1
        assert messages[0]["role"] == "user"
        assert messages[0]["content"] == "Test query"

    def test_message_construction_with_history(self, ai_generator_with_mock):
        """Test message construction with conversation history"""
        ai_gen = ai_generator_with_mock
        
        history = "User: Hi\nAssistant: Hello!"
        ai_gen.generate_response("What's next?", conversation_history=history)
        
        call_args = ai_gen.client.messages.create.call_args
        system_content = call_args[1]["system"]
        
        # System prompt should include history
        assert AIGenerator.SYSTEM_PROMPT in system_content
        assert "Previous conversation:" in system_content
        assert history in system_content

    def test_tool_result_message_construction(self, ai_generator_with_mock, tool_manager):
        """Test message construction during tool execution"""
        ai_gen = ai_generator_with_mock
        
        # Mock tool use response
        initial_response = Mock()
        initial_response.stop_reason = "tool_use"
        initial_response.content = [Mock()]
        initial_response.content[0].type = "tool_use"
        initial_response.content[0].name = "search_course_content"
        initial_response.content[0].input = {"query": "test"}
        initial_response.content[0].id = "call_123"
        
        final_response = Mock()
        final_response.content = [Mock()]
        final_response.content[0].text = "Final answer"
        
        ai_gen.client.messages.create.side_effect = [initial_response, final_response]
        
        with patch.object(tool_manager, 'execute_tool') as mock_execute:
            mock_execute.return_value = "Tool result"
            
            ai_gen.generate_response(
                "Test query",
                tools=tool_manager.get_tool_definitions(),
                tool_manager=tool_manager
            )
            
            # Check the second API call (after tool execution)
            second_call_args = ai_gen.client.messages.create.call_args_list[1]
            messages = second_call_args[1]["messages"]
            
            # Should have: user message, assistant tool use, user tool results
            assert len(messages) == 3
            assert messages[0]["role"] == "user"  # Original query
            assert messages[1]["role"] == "assistant"  # Tool use response
            assert messages[2]["role"] == "user"  # Tool results


class TestAIGeneratorErrorHandling:
    """Test error handling in AIGenerator"""

    def test_anthropic_api_error_handling(self, test_config):
        """Test handling of Anthropic API errors"""
        ai_gen = AIGenerator(test_config.ANTHROPIC_API_KEY, test_config.ANTHROPIC_MODEL)
        
        # Mock client to raise an exception
        with patch.object(ai_gen.client.messages, 'create') as mock_create:
            mock_create.side_effect = Exception("API error")
            
            # Should raise the exception (not catch it)
            with pytest.raises(Exception) as exc_info:
                ai_gen.generate_response("Test query")
            
            assert "API error" in str(exc_info.value)

    def test_handle_tool_execution_missing_tool_manager(self, ai_generator_with_mock):
        """Test _handle_tool_execution when tool_manager is None"""
        ai_gen = ai_generator_with_mock
        
        # Create mock response that would trigger tool execution
        mock_response = Mock()
        mock_response.stop_reason = "tool_use"
        mock_response.content = []
        
        base_params = {"messages": [], "system": "test"}
        
        # Should handle gracefully when no tool_manager provided
        result = ai_gen._handle_tool_execution(mock_response, base_params, None)
        
        # Should make API call without tool results
        assert ai_gen.client.messages.create.call_count >= 1


class TestAIGeneratorConfiguration:
    """Test AIGenerator configuration and parameters"""

    def test_base_params_configuration(self, test_config):
        """Test that base_params are properly configured"""
        ai_gen = AIGenerator(test_config.ANTHROPIC_API_KEY, test_config.ANTHROPIC_MODEL)
        
        expected_params = {
            "model": test_config.ANTHROPIC_MODEL,
            "temperature": 0,
            "max_tokens": 800
        }
        
        assert ai_gen.base_params == expected_params

    def test_different_model_configuration(self):
        """Test AIGenerator with different model"""
        different_model = "claude-3-haiku-20240307"
        ai_gen = AIGenerator("test-key", different_model)
        
        assert ai_gen.model == different_model
        assert ai_gen.base_params["model"] == different_model