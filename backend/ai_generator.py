import anthropic
from typing import List, Optional, Dict, Any

class AIGenerator:
    """Handles interactions with Anthropic's Claude API for generating responses"""
    
    # Static system prompt to avoid rebuilding on each call
    SYSTEM_PROMPT = """ You are an AI assistant specialized in course materials and educational content with access to comprehensive search tools for course information.

Tool Usage Guidelines:
- **Course outline/structure questions**: Use get_course_outline tool to get complete course information including title, course link, and all lessons with their numbers and titles
- **Content-specific questions**: Use search_course_content tool for questions about specific educational materials or lesson content
- **Up to 2 sequential tool calls maximum** - use multiple rounds for complex queries requiring comparisons or multi-step reasoning
- Synthesize tool results into accurate, fact-based responses
- If tool yields no results, state this clearly without offering alternatives

Sequential Tool Strategy:
- **First round**: Gather primary information related to the query
- **Second round**: Use first round results to gather additional context, make comparisons, or fill information gaps
- **Complex queries**: Break down into sequential searches (e.g., get course outline, then search specific lesson content)
- **Comparison queries**: Use separate searches for each item being compared
- **Multi-part questions**: Use results from first search to inform second search

Response Protocol:
- **General knowledge questions**: Answer using existing knowledge without using tools
- **Course outline questions** (e.g., "What is the outline of X course?"): Use get_course_outline tool first, then provide complete course information
- **Course content questions**: Use search_course_content tool first, then answer
- **Comparison questions**: Use sequential searches to gather information about each item being compared
- **No meta-commentary**:
 - Provide direct answers only — no reasoning process, tool usage explanations, or question-type analysis
 - Do not mention "based on the search results", "using the outline tool", "in my first search", or "in my second search"

All responses must be:
1. **Brief, Concise and focused** - Get to the point quickly
2. **Educational** - Maintain instructional value
3. **Clear** - Use accessible language
4. **Example-supported** - Include relevant examples when they aid understanding
5. **Comprehensive** - Use all available tool results to provide complete answers
Provide only the direct answer to what was asked.
"""
    
    def __init__(self, api_key: str, model: str):
        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = model
        
        # Pre-build base API parameters
        self.base_params = {
            "model": self.model,
            "temperature": 0,
            "max_tokens": 800
        }
    
    def generate_response(self, query: str,
                         conversation_history: Optional[str] = None,
                         tools: Optional[List] = None,
                         tool_manager=None) -> str:
        """
        Generate AI response with optional tool usage and conversation context.
        
        Args:
            query: The user's question or request
            conversation_history: Previous messages for context
            tools: Available tools the AI can use
            tool_manager: Manager to execute tools
            
        Returns:
            Generated response as string
        """
        
        # Build system content efficiently - avoid string ops when possible
        system_content = (
            f"{self.SYSTEM_PROMPT}\n\nPrevious conversation:\n{conversation_history}"
            if conversation_history 
            else self.SYSTEM_PROMPT
        )
        
        # Prepare API call parameters efficiently
        api_params = {
            **self.base_params,
            "messages": [{"role": "user", "content": query}],
            "system": system_content
        }
        
        # Add tools if available
        if tools:
            api_params["tools"] = tools
            api_params["tool_choice"] = {"type": "auto"}
        
        # Get response from Claude
        response = self.client.messages.create(**api_params)
        
        # Handle tool execution if needed
        if response.stop_reason == "tool_use" and tool_manager:
            return self._handle_tool_execution(response, api_params, tool_manager)
        
        # Return direct response
        return response.content[0].text
    
    def _handle_tool_execution(self, initial_response, base_params: Dict[str, Any], tool_manager):
        """
        Handle sequential tool execution with iterative approach.
        Supports up to 2 rounds of tool calls per user query.
        
        Args:
            initial_response: The response containing tool use requests
            base_params: Base API parameters
            tool_manager: Manager to execute tools
            
        Returns:
            Final response text after tool execution
        """
        messages = base_params["messages"].copy()
        current_response = initial_response
        round_count = 0
        MAX_ROUNDS = 2
        
        while round_count < MAX_ROUNDS:
            round_count += 1
            
            # Add AI's response (with tool_use blocks) to conversation
            messages.append({"role": "assistant", "content": current_response.content})
            
            # Execute all tool calls from current response
            tool_results = self._execute_tools_from_response(current_response, tool_manager)
            
            if not tool_results:
                # No tools were executed - break the loop
                break
                
            # Add tool results to conversation
            messages.append({"role": "user", "content": tool_results})
            
            # Check if we've reached max rounds
            if round_count >= MAX_ROUNDS:
                # Final call without tools to force completion
                return self._make_final_api_call(messages, base_params)
            
            # Make next API call with tools still available
            try:
                current_response = self._make_intermediate_api_call(messages, base_params)
                
                # Check if Claude made more tool calls
                if current_response.stop_reason != "tool_use":
                    # Claude chose not to use more tools - return response
                    return current_response.content[0].text
                    
            except Exception as e:
                # Handle API errors gracefully - fallback to final call
                return self._make_final_api_call(messages, base_params)
        
        # If we exit the loop, make final call
        return self._make_final_api_call(messages, base_params)
    
    def _execute_tools_from_response(self, response, tool_manager) -> List[Dict]:
        """Extract and execute all tool calls from a response"""
        tool_results = []
        
        for content_block in response.content:
            if content_block.type == "tool_use":
                try:
                    tool_result = tool_manager.execute_tool(
                        content_block.name, 
                        **content_block.input
                    )
                    
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": content_block.id,
                        "content": tool_result
                    })
                except Exception as e:
                    # Handle individual tool failures gracefully
                    tool_results.append({
                        "type": "tool_result", 
                        "tool_use_id": content_block.id,
                        "content": f"Tool execution failed: {str(e)}"
                    })
                    
        return tool_results

    def _make_intermediate_api_call(self, messages, base_params):
        """Make API call with tools still available for next round"""
        api_params = {
            **self.base_params,
            "messages": messages,
            "system": base_params["system"],
            "tools": base_params.get("tools"),  # Keep tools available
            "tool_choice": {"type": "auto"}
        }
        
        return self.client.messages.create(**api_params)

    def _make_final_api_call(self, messages, base_params):
        """Make final API call without tools to force completion"""
        final_params = {
            **self.base_params,
            "messages": messages,
            "system": base_params["system"]
            # No tools - forces Claude to provide final answer
        }
        
        final_response = self.client.messages.create(**final_params)
        return final_response.content[0].text