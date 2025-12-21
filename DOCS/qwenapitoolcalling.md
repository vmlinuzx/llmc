# Qwen API Tool Calling Guide

This document explains how to properly structure and use tool calling with the Qwen API.

## Overview

Tool calling in Qwen allows the model to interact with external functions or services during the conversation. The model can suggest which functions to call based on user input, and you can execute those functions and return the results to the model.

## Basic Structure

### Function Definition Format

When defining functions for the model to use, you need to provide a JSON schema that describes each function:

```json
{
  "functions": [
    {
      "name": "function_name",
      "description": "Brief description of what the function does",
      "parameters": {
        "type": "object",
        "properties": {
          "param1": {
            "type": "string",
            "description": "Description of parameter 1"
          },
          "param2": {
            "type": "integer",
            "description": "Description of parameter 2"
          }
        },
        "required": ["param1"]
      }
    }
  ]
}
```

### Tool Call Response Format

When the model decides to call a function, it will return a response with the following structure:

```json
{
  "choices": [
    {
      "message": {
        "role": "assistant",
        "content": null,
        "tool_calls": [
          {
            "id": "call_abc123",
            "function": {
              "name": "function_name",
              "arguments": "{\"param1\": \"value1\", \"param2\": 42}"
            },
            "type": "function"
          }
        ]
      }
    }
  ]
}
```

## Complete Example Flow

### Step 1: Define Functions

First, define the functions you want the model to be able to call:

```json
{
  "model": "qwen-max", // or another Qwen model
  "messages": [
    {
      "role": "user",
      "content": "What's the weather in Beijing today?"
    }
  ],
  "tools": [
    {
      "type": "function",
      "function": {
        "name": "get_current_weather",
        "description": "Get the current weather in a given location",
        "parameters": {
          "type": "object",
          "properties": {
            "location": {
              "type": "string",
              "description": "The city and state, e.g. San Francisco, CA"
            },
            "unit": {
              "type": "string",
              "enum": ["celsius", "fahrenheit"]
            }
          },
          "required": ["location"]
        }
      }
    }
  ]
}
```

### Step 2: Handle Model Response

The model may respond with a tool call suggestion:

```json
{
  "id": "chatcmpl-...",
  "object": "chat.completion",
  "created": 1677825435,
  "model": "qwen-max",
  "choices": [
    {
      "index": 0,
      "message": {
        "role": "assistant",
        "content": null,
        "tool_calls": [
          {
            "id": "call_abc123",
            "function": {
              "name": "get_current_weather",
              "arguments": "{\"location\": \"Beijing, China\", \"unit\": \"celsius\"}"
            },
            "type": "function"
          }
        ]
      },
      "finish_reason": "tool_calls"
    }
  ]
}
```

### Step 3: Execute Tool Calls

Execute the suggested function with the provided arguments:

```json
{
  "name": "get_current_weather",
  "arguments": "{\"location\": \"Beijing, China\", \"unit\": \"celsius\"}"
}
```

### Step 4: Return Results to Model

Send the function result back to the model in the conversation history:

```json
{
  "model": "qwen-max",
  "messages": [
    {
      "role": "user",
      "content": "What's the weather in Beijing today?"
    },
    {
      "role": "assistant",
      "tool_calls": [
        {
          "id": "call_abc123",
          "function": {
            "name": "get_current_weather",
            "arguments": "{\"location\": \"Beijing, China\", \"unit\": \"celsius\"}"
          },
          "type": "function"
        }
      ]
    },
    {
      "role": "tool",
      "name": "get_current_weather",
      "content": "{\"temperature\": 15, \"unit\": \"celsius\", \"description\": \"Partly cloudy\"}",
      "tool_call_id": "call_abc123"
    }
  ]
}
```

## Best Practices

### 1. Clear Descriptions
Provide clear, concise descriptions for both functions and parameters to help the model understand when and how to use them.

### 2. Proper Parameter Types
Use appropriate JSON Schema types (`string`, `number`, `integer`, `boolean`, `array`, `object`) for parameters.

### 3. Required Parameters
Always specify which parameters are required in the `required` array.

### 4. Enum Values
For parameters with limited options, use the `enum` property to constrain possible values.

### 5. Error Handling
Handle potential errors from tool calls gracefully and consider how to communicate failures back to the model.

## Advanced Patterns

### Multiple Tool Calls
The model can suggest multiple tool calls in a single response:

```json
{
  "tool_calls": [
    {
      "id": "call_1",
      "function": {
        "name": "function_a",
        "arguments": "{\"param\": \"value\"}"
      },
      "type": "function"
    },
    {
      "id": "call_2",
      "function": {
        "name": "function_b",
        "arguments": "{\"other_param\": \"other_value\"}"
      },
      "type": "function"
    }
  ]
}
```

### Parallel Execution
You can execute multiple tool calls in parallel if they don't depend on each other, then return all results together.

## Common Mistakes to Avoid

1. **Missing Content**: When returning tool results, ensure the `content` field contains a JSON string with the function's output.
2. **Incorrect Role**: Use `"role": "tool"` for tool responses, not `"role": "assistant"`.
3. **Mismatched IDs**: Ensure the `tool_call_id` in the tool response matches the ID from the assistant's tool call suggestion.
4. **Invalid JSON**: Make sure all `arguments` values are valid JSON strings.

## Troubleshooting

If tool calling isn't working as expected:

1. Verify that your function definitions follow the correct JSON Schema format
2. Check that the model you're using supports tool calling
3. Ensure your API requests include the functions/tools in the correct format
4. Validate that your function call responses have the proper structure

## Special Case: Qwen Code Environment

When running within the Qwen Code environment (such as when using Qwen Code in VS Code), the tool definitions are automatically provided to the model at startup. This means that all the tools available to the assistant (like `read_file`, `write_file`, `edit`, `grep_search`, etc.) are already registered and available for use without requiring explicit function definitions in each request.

In this environment, the tool calling follows the same pattern described above, but the tools are pre-configured. For example, when you ask to read a file, the system automatically handles the tool call interaction between you, the interface, and the model.

The tools available in the Qwen Code environment typically include:

- `read_file` - Reads content from a specified file
- `write_file` - Writes content to a specified file
- `edit` - Replaces text within a file
- `grep_search` - Searches for patterns in files
- `glob` - Finds files matching a pattern
- `run_shell_command` - Executes shell commands
- `list_directory` - Lists directory contents
- `read_many_files` - Reads content from multiple files
- `web_fetch` - Fetches and processes content from URLs
- `web_search` - Performs web searches
- `save_memory` - Saves information to long-term memory
- `todo_write` - Creates and manages task lists
- `task` - Launches specialized agents
- `exit_plan_mode` - Exits plan mode when planning implementations

This automatic tool registration allows for seamless integration with the development environment, enabling powerful workflows without manual tool configuration.