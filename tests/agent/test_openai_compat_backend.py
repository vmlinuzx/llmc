import pytest
import respx
import httpx
from llmc_agent.backends.openai_compat import OpenAICompatBackend
from llmc_agent.backends.base import GenerateRequest

# Define custom exceptions as per SDD
class AuthenticationError(Exception):
    pass

class RateLimitError(Exception):
    pass

class APIError(Exception):
    pass

class InternalServerError(APIError):
    pass

class NotFoundError(Exception):
    pass

@pytest.fixture
def backend():
    return OpenAICompatBackend(base_url="http://localhost:8080/v1")

@pytest.fixture
def generate_request():
    return GenerateRequest(
        system="System prompt",
        messages=[{"role": "user", "content": "Hello"}],
        model="test-model"
    )

@pytest.fixture
def tools():
    return [{
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "Get current weather",
            "parameters": {
                "type": "object",
                "properties": {
                    "location": {"type": "string"}
                }
            }
        }
    }]

@pytest.mark.asyncio
@respx.mock
async def test_generate_with_tools_success(backend, generate_request, tools):
    # Test Case 1: Content Response
    content_response = {
        "choices": [{
            "message": {"role": "assistant", "content": "Hello!"},
            "finish_reason": "stop"
        }],
        "usage": {"prompt_tokens": 10, "completion_tokens": 5},
        "model": "test-model"
    }
    respx.post("http://localhost:8080/v1/chat/completions").mock(
        return_value=httpx.Response(200, json=content_response)
    )

    response = await backend.generate_with_tools(generate_request, tools)
    assert response.content == "Hello!"
    assert response.tool_calls == []
    assert response.tokens_prompt == 10
    assert response.tokens_completion == 5

    # Test Case 2: Tool Calls Response
    tool_calls_response = {
        "choices": [{
            "message": {
                "role": "assistant",
                "content": None,
                "tool_calls": [{
                    "id": "call_123",
                    "type": "function",
                    "function": {
                        "name": "get_weather",
                        "arguments": '{"location": "San Francisco"}'
                    }
                }]
            },
            "finish_reason": "tool_calls"
        }],
        "usage": {"prompt_tokens": 15, "completion_tokens": 10},
        "model": "test-model"
    }
    respx.post("http://localhost:8080/v1/chat/completions").mock(
        return_value=httpx.Response(200, json=tool_calls_response)
    )

    response = await backend.generate_with_tools(generate_request, tools)
    assert response.content == ""
    assert len(response.tool_calls) == 1
    assert response.tool_calls[0]["function"]["name"] == "get_weather"
    assert response.tool_calls[0]["function"]["arguments"] == '{"location": "San Francisco"}'
    assert response.tool_calls[0]["id"] == "call_123"

@pytest.mark.asyncio
@respx.mock
async def test_generate_errors(backend, generate_request):
    # Test Case 1: 401 Unauthorized
    respx.post("http://localhost:8080/v1/chat/completions").mock(return_value=httpx.Response(401))
    with pytest.raises(AuthenticationError):
        await backend.generate(generate_request)

    # Test Case 2: 429 Too Many Requests
    respx.post("http://localhost:8080/v1/chat/completions").mock(return_value=httpx.Response(429))
    with pytest.raises(RateLimitError):
        await backend.generate(generate_request)

    # Test Case 3: 500 Internal Server Error
    respx.post("http://localhost:8080/v1/chat/completions").mock(return_value=httpx.Response(500))
    with pytest.raises((APIError, InternalServerError)):
        await backend.generate(generate_request)

    # Test Case 4: 404 Not Found
    respx.post("http://localhost:8080/v1/chat/completions").mock(return_value=httpx.Response(404))
    with pytest.raises(NotFoundError):
        await backend.generate(generate_request)

@pytest.mark.asyncio
@respx.mock
async def test_generate_stream_errors(backend, generate_request):
    # Test Case 1: 401 Unauthorized
    respx.post("http://localhost:8080/v1/chat/completions").mock(return_value=httpx.Response(401))
    with pytest.raises(AuthenticationError):
        async for _ in backend.generate_stream(generate_request):
            pass

    # Test Case 2: 429 Too Many Requests
    respx.post("http://localhost:8080/v1/chat/completions").mock(return_value=httpx.Response(429))
    with pytest.raises(RateLimitError):
        async for _ in backend.generate_stream(generate_request):
            pass

    # Test Case 3: 500 Internal Server Error
    respx.post("http://localhost:8080/v1/chat/completions").mock(return_value=httpx.Response(500))
    with pytest.raises((APIError, InternalServerError)):
        async for _ in backend.generate_stream(generate_request):
            pass

    # Test Case 4: 404 Not Found
    respx.post("http://localhost:8080/v1/chat/completions").mock(return_value=httpx.Response(404))
    with pytest.raises(NotFoundError):
        async for _ in backend.generate_stream(generate_request):
            pass

@pytest.mark.asyncio
@respx.mock
async def test_generate_with_tools_errors(backend, generate_request):
    tools = [{
        "type": "function",
        "function": {
            "name": "test_tool",
            "description": "A test tool",
            "parameters": {"type": "object", "properties": {}}
        }
    }]

    # Test Case 1: 401 Unauthorized
    respx.post("http://localhost:8080/v1/chat/completions").mock(return_value=httpx.Response(401))
    with pytest.raises(AuthenticationError):
        await backend.generate_with_tools(generate_request, tools)

    # Test Case 2: 429 Too Many Requests
    respx.post("http://localhost:8080/v1/chat/completions").mock(return_value=httpx.Response(429))
    with pytest.raises(RateLimitError):
        await backend.generate_with_tools(generate_request, tools)

    # Test Case 3: 500 Internal Server Error
    respx.post("http://localhost:8080/v1/chat/completions").mock(return_value=httpx.Response(500))
    with pytest.raises((APIError, InternalServerError)):
        await backend.generate_with_tools(generate_request, tools)

    # Test Case 4: 404 Not Found
    respx.post("http://localhost:8080/v1/chat/completions").mock(return_value=httpx.Response(404))
    with pytest.raises(NotFoundError):
        await backend.generate_with_tools(generate_request, tools)
