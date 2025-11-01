# LLM Gateway - Simple Local-First AI Tool

## What It Does

Dead simple LLM gateway that tries local Ollama first, falls back to Gemini API on failure.

## Setup

### 1. Make scripts executable
```bash
chmod +x scripts/llm_gateway.sh
chmod +x scripts/call_graybeard.sh
chmod +x scripts/test_llm_gateway.sh
```

### 2. Set up Gemini API key (for fallback)
```bash
# Add to .env.local
echo "GEMINI_API_KEY=your-key-here" >> .env.local

# Or export it
export GEMINI_API_KEY="your-key-here"
```

Get a free key: https://aistudio.google.com/app/apikey

## Usage

### Basic Usage

```bash
# Via pipe
echo "Explain async/await in JavaScript" | ./scripts/llm_gateway.sh

# Via argument
./scripts/llm_gateway.sh "What is the difference between let and const?"

# Force API (skip local)
./scripts/llm_gateway.sh --api "Complex reasoning task here"

# Force local only
./scripts/llm_gateway.sh --local "Simple task"
```

### Call the Graybeard (Auto-analyze test failures)

```bash
# Run tests with auto-analysis on failure
npm test || ./scripts/call_graybeard.sh

# Or add to your test script in package.json
{
  "scripts": {
    "test:debug": "npm test || ./scripts/call_graybeard.sh"
  }
}
```

## How It Works

1. **Try Local First** (free, slower)
   - Uses Ollama with qwen2.5:14b-instruct (best coding model you have)
   - Runs on your RTX 2000 Ada (8GB VRAM)
   - ~5-10 tokens/sec

2. **Fallback to API** (cheap, fast)
   - Uses Gemini 2.0 Flash (the hot shit right now)
   - Cost: $0.075 per 1M tokens
   - ~100+ tokens/sec

## Cost Estimate

```
Typical usage with smart fallback:
- 80% local (free)
- 20% API at $0.075/1M

Your 400K token day:
- 320K local: $0
- 80K API: $0.006
Total: Less than 1 cent per day

Monthly: ~$0.20 vs $40 subscriptions
```

## Models Available (Your Ollama)

```
Best for coding:
- qwen2.5:14b-instruct-q4_K_M (default, 9GB)
- deepseek-r1:7b (reasoning, 4.7GB)

Best for speed:
- qwen2.5:7b-instruct (4.7GB)
- llama3.1:8b-instruct (4.9GB)

Specialized:
- gemma2:9b (Google's model, 5.8GB)
- dolphin-mistral:7b (uncensored, 4GB)
```

## Testing

```bash
# Run test suite
./scripts/test_llm_gateway.sh

# Should see 3 tests:
# 1. Pipe input
# 2. Command line arg  
# 3. Force API flag
```

## Integration with Codex

Update `codex_wrap.sh` to use the gateway:

```bash
# Before running Codex, try LLM gateway for simple tasks
if [[ "$SIMPLE_TASK" == "true" ]]; then
  echo "$USER_PROMPT" | ./scripts/llm_gateway.sh
else
  # Use Codex for complex work
  codex "$USER_PROMPT"
fi
```

## Troubleshooting

**Ollama not responding:**
```bash
# Check if Ollama is running
curl http://localhost:11434/api/tags

# If not, start it
ollama serve
```

**API key not working:**
```bash
# Test API key
curl "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash-exp:generateContent?key=$GEMINI_API_KEY" \
  -H 'Content-Type: application/json' \
  -d '{"contents":[{"parts":[{"text":"test"}]}]}'
```

**Model too slow:**
Use a smaller model in `llm_gateway.js`:
```javascript
const OLLAMA_MODEL = 'qwen2.5:7b-instruct'; // Faster
```

## What's Next

- [ ] Add token counting/cost tracking
- [ ] Add caching for repeated queries
- [ ] Add timeout configuration
- [ ] Add model selection via CLI arg
- [ ] Integration with codex_wrap.sh

## Files Created

- `scripts/llm_gateway.js` - Main tool (Node.js)
- `scripts/llm_gateway.sh` - Bash wrapper
- `scripts/call_graybeard.sh` - Test failure analyzer
- `scripts/test_llm_gateway.sh` - Test suite
- `scripts/LLM_GATEWAY_README.md` - This file

Total lines of code: ~200
Time to ship: Done in one session
Cost savings: $40/month → $0.20/month for most work
