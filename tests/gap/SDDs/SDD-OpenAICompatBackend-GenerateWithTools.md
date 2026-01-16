# SDD: OpenAICompatBackend-GenerateWithTools

## 1. Gap Description
The `generate_with_tools` method in `llmc_agent/backends/openai_compat.py` is currently untested. This method is responsible for handling tool-calling with OpenAI-compatible backends. Without tests, we cannot ensure its correctness, especially regarding the request payload format and the parsing of the response, including tool calls.

## 2. Target Location
The tests should be added to the newly created test file: `tests/agent/test_openai_compat_backend.py`.

## 3. Test Strategy
We will use `pytest` and `respx` to mock the API responses for the `generate_with_tools` method. We need to test two main scenarios:
1.  The model returns a regular content response.
2.  The model returns one or more tool calls.

- **Test Case 1: Content Response:** The test will assert that the `content` field in the `GenerateResponse` is correctly populated and that the `tool_calls` list is empty.
- **Test Case 2: Tool Calls Response:** The test will mock a response containing one or more tool calls in the OpenAI format. The test will then assert that the `tool_calls` field in the `GenerateResponse` is a correctly parsed list of tool call dictionaries.

## 4. Implementation Details
- Add new tests to `tests/agent/test_openai_compat_backend.py`.
- Use the existing `backend` and `generate_request` fixtures.
- Create a `tools` fixture that provides a sample list of tools in the OpenAI format.
- **For Test Case 1:**
    - Mock a successful response (`200 OK`) with a standard OpenAI chat completion payload (no tool calls).
    - Call `backend.generate_with_tools(request, tools)`.
    - Assert that the response's `content` is as expected and `tool_calls` is an empty list.
- **For Test Case 2:**
    - Mock a successful response (`200 OK`) with an OpenAI payload that includes a `tool_calls` array in the `message`.
    - Call `backend.generate_with_tools(request, tools)`.
    - Assert that the response's `tool_calls` list contains the correctly normalized tool call objects.
    - Check that the `name`, `arguments`, and `id` of the function call are correctly extracted.
