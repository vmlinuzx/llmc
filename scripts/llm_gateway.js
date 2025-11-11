#!/usr/bin/env node
/**
 * llm_gateway.js - Simple LLM tool: Local first, API fallback
 * Usage: echo "prompt" | node llm_gateway.js
 *        node llm_gateway.js "prompt text"
 *        node llm_gateway.js --api "prompt text"     (skip local, use Azure/Claude/Gemini)
 *        node llm_gateway.js --claude "prompt text"  (force Claude API)
 *        node llm_gateway.js --local "prompt text"   (force local Ollama)
 */

const http = require('http');
const https = require('https');
const fs = require('fs');
const path = require('path');
const { spawnSync } = require('child_process');
const { renderSlice } = require(path.join(__dirname, '..', 'node', 'contracts_loader'));

function loadEnvFrom(file) {
  try {
    const resolved = path.resolve(file);
    if (!fs.existsSync(resolved)) return;
    const txt = fs.readFileSync(resolved, 'utf8');
    for (const line of txt.split(/\r?\n/)) {
      if (!line || line.startsWith('#')) continue;
      const match = line.match(/^([A-Z0-9_]+)=(.*)$/);
      if (!match) continue;
      const key = match[1];
      let val = match[2].trim();
      const semicolonIdx = val.indexOf(';');
      if (semicolonIdx !== -1) {
        val = val.slice(0, semicolonIdx).trim();
      }
      if (
        (val.startsWith('"') && val.endsWith('"')) ||
        (val.startsWith("'") && val.endsWith("'"))
      ) {
        val = val.slice(1, -1);
      }
      if (!Object.prototype.hasOwnProperty.call(process.env, key)) {
        process.env[key] = val;
      }
    }
  } catch (_) {
    // Ignore env loading errors
  }
}

const EXEC_ROOT = path.resolve(__dirname, '..');
if (!process.env.LLMC_EXEC_ROOT) {
  process.env.LLMC_EXEC_ROOT = EXEC_ROOT;
}
let repoOverride = null;

loadEnvFrom(path.join(EXEC_ROOT, '.env.local'));
loadEnvFrom(path.join(process.cwd(), '.env.local'));

// Config
const MODELS = {
  code: 'qwen2.5:14b-instruct-q4_K_M',
  uncensored: 'gpt-oss:20b',
  fast: 'deepseek-coder:6.7b'
};

const requestedProfileRaw = (process.env.OLLAMA_PROFILE || '').trim();
const requestedModelOverride = (process.env.OLLAMA_MODEL || '').trim();
const hasModelOverride = requestedModelOverride.length > 0;
const resolvedProfile = MODELS[requestedProfileRaw] ? requestedProfileRaw : 'code';
const profileLabel = hasModelOverride
  ? (MODELS[requestedProfileRaw] ? requestedProfileRaw : 'custom')
  : resolvedProfile;

const OLLAMA_URL = process.env.OLLAMA_URL || 'http://localhost:11434';
const OLLAMA_MODEL = hasModelOverride ? requestedModelOverride : MODELS[resolvedProfile];
const ANTHROPIC_API_KEY = process.env.ANTHROPIC_API_KEY || '';
const ANTHROPIC_MODEL = process.env.ANTHROPIC_MODEL || 'claude-sonnet-4-20250514';
const ANTHROPIC_BASE_URL = process.env.ANTHROPIC_BASE_URL || 'https://api.anthropic.com';
const ANTHROPIC_VERSION = process.env.ANTHROPIC_VERSION || '2023-06-01';
const ANTHROPIC_MAX_TOKENS = Number.parseInt(process.env.ANTHROPIC_MAX_TOKENS || '4096', 10);
const MINIMAX_API_KEY = process.env.MINIMAXKEY2 || '';
const MINIMAX_BASE_URL = process.env.MINIMAX_BASE_URL || 'https://api.minimax.chat/v1';
const MINIMAX_MODEL = process.env.MINIMAX_MODEL || 'abab6-chat'; // Default MiniMax model
const MINIMAX_AVAILABLE = Boolean(MINIMAX_API_KEY);
const ANTHROPIC_AVAILABLE = Boolean(ANTHROPIC_API_KEY);
const AZURE_ENDPOINT = (process.env.AZURE_OPENAI_ENDPOINT || '').replace(/\/$/, '');
const AZURE_KEY = process.env.AZURE_OPENAI_KEY || '';
const AZURE_DEPLOYMENT = process.env.AZURE_OPENAI_DEPLOYMENT || '';
const AZURE_DEPLOYMENT_CODEX = process.env.AZURE_OPENAI_DEPLOYMENT_CODEX || '';
const AZURE_DEPLOYMENT_CODEX_LIST =
  process.env.AZURE_OPENAI_DEPLOYMENT_CODEX_LIST || '';
const AZURE_API_VERSION = process.env.AZURE_OPENAI_API_VERSION || '2024-02-15-preview';
const AZURE_AVAILABLE = Boolean(AZURE_ENDPOINT && AZURE_KEY && AZURE_DEPLOYMENT);
const AZURE_CODEX_AVAILABLE = Boolean(
  AZURE_ENDPOINT &&
    AZURE_KEY &&
    (AZURE_DEPLOYMENT_CODEX || AZURE_DEPLOYMENT_CODEX_LIST || AZURE_DEPLOYMENT)
);
const AZURE_FORCE_COMPLETION = envFlag('AZURE_OPENAI_FORCE_COMPLETION') || /gpt-5/i.test(AZURE_DEPLOYMENT);
const AZURE_MAX_TOKENS = Number.parseInt(process.env.AZURE_OPENAI_MAX_TOKENS || '1024', 10);
const AZURE_TEMPERATURE_RAW = process.env.AZURE_OPENAI_TEMPERATURE;
const AZURE_TEMPERATURE = (() => {
  if (AZURE_TEMPERATURE_RAW === undefined || AZURE_TEMPERATURE_RAW === '') {
    return AZURE_FORCE_COMPLETION ? null : 0;
  }
  const parsed = Number(AZURE_TEMPERATURE_RAW);
  return Number.isFinite(parsed) ? parsed : null;
})();
const BASH_EXECUTABLE = resolveBashExecutable();


// Parse args
const args = process.argv.slice(2);
const debugEnabled = args.includes('--debug') || args.includes('-d');
const forceAPI = args.includes('--api') || args.includes('-a');
const forceLocal = args.includes('--local') || args.includes('-l');
const forceClaude = args.includes('--claude') || args.includes('-c');
const forceGemini = args.includes('--gemini') || args.includes('-g');
const forceGeminiAPI = args.includes('--gemini-api');
const forceYolo = args.includes('--yolo') || args.includes('-y');
const forceAzureCodex = args.includes('--azure-codex');
const forceMiniMax = args.includes('--minimax');
let azureModelOverride = '';
const promptParts = [];

for (let i = 0; i < args.length; i++) {
  const arg = args[i];
  if (arg === '--azure-model') {
    if (i + 1 < args.length) {
      azureModelOverride = args[i + 1];
      i += 1;
    }
    continue;
  }
  if (arg.startsWith('--azure-model=')) {
    azureModelOverride = arg.slice('--azure-model='.length);
    continue;
  }
  if (arg === '--repo') {
    if (i + 1 < args.length) {
      repoOverride = args[i + 1];
      i += 1;
    }
    continue;
  }
  if (arg.startsWith('--repo=')) {
    repoOverride = arg.slice('--repo='.length);
    continue;
  }
  if (
    arg === '--azure-codex' ||
    arg === '--api' ||
    arg === '--local' ||
    arg === '--claude' ||
    arg === '--gemini' ||
    arg === '--gemini-api' ||
    arg === '--yolo' ||
    arg === '--debug' ||
    arg === '-a' ||
    arg === '-l' ||
    arg === '-c' ||
    arg === '-g' ||
    arg === '-y' ||
    arg === '-d' ||
    arg === '--minimax'
  ) {
    continue;
  }
  if (arg.startsWith('-')) {
    continue;
  }
  promptParts.push(arg);
}

let prompt = promptParts.join(' ');
const debugLog = (...messages) => {
  if (debugEnabled) {
    console.error('[debug]', ...messages);
  }
};

const resolvedRepoRoot = path.resolve(
  repoOverride ||
    process.env.LLMC_TARGET_REPO ||
    process.env.LLMC_REPO_ROOT ||
    process.cwd()
);
loadEnvFrom(path.join(resolvedRepoRoot, '.env.local'));

const REPO_ROOT = resolvedRepoRoot;
process.env.LLMC_TARGET_REPO = REPO_ROOT;

const RAG_HELPER = path.join(EXEC_ROOT, 'scripts', 'rag_plan_helper.sh');
const PYTHON_BIN = process.env.LLM_GATEWAY_PYTHON || process.env.PYTHON || 'python3';

// RAG Configuration
const RAG_ENABLED = envFlag('RAG_ENABLED') || false;
const RAG_TIMEOUT_MS = Number.parseInt(process.env.RAG_TIMEOUT_MS || '800', 10);
const RAG_TOP_K = Number.parseInt(process.env.RAG_TOP_K || '8', 10);
const RAG_MIN_SCORE = Number.parseFloat(process.env.RAG_MIN_SCORE || '0.35');
const RAG_MAX_CHARS = Number.parseInt(process.env.RAG_MAX_CHARS || '12000', 10);
const RAG_FAIL_OPEN = envFlag('RAG_FAIL_OPEN') !== false; // default true
const RAG_LOG_SAMPLE_RATE = Number.parseFloat(process.env.RAG_LOG_SAMPLE_RATE || '1.0');
const RAG_PROVENANCE = envFlag('RAG_PROVENANCE') || false;

// Debug: Log RAG configuration
if (RAG_LOG_SAMPLE_RATE >= 1.0) {
  console.error(JSON.stringify({
    event: 'rag.config',
    ragEnabled: RAG_ENABLED,
    ragEnabledRaw: process.env.RAG_ENABLED,
    timeoutMs: RAG_TIMEOUT_MS,
    topK: RAG_TOP_K,
    minScore: RAG_MIN_SCORE,
    maxChars: RAG_MAX_CHARS,
    failOpen: RAG_FAIL_OPEN,
    logSampleRate: RAG_LOG_SAMPLE_RATE,
    provenance: RAG_PROVENANCE,
    service: 'llm_gateway'
  }));
}

// Generate correlation ID for telemetry
function generateCorrelationId() {
  return Date.now().toString(36) + '-' + Math.random().toString(36).substr(2, 9);
}

// Read from stdin if no prompt provided
if (!prompt && !process.stdin.isTTY) {
  let stdinData = '';
  process.stdin.on('data', chunk => stdinData += chunk);
  process.stdin.on('end', () => {
    prompt = stdinData.trim();
    main();
  });
} else {
  main();
}

async function main() {
  if (!prompt) {
    console.error('Usage: echo "prompt" | node llm_gateway.js');
    console.error('       node llm_gateway.js "prompt text"');
    console.error('       node llm_gateway.js --api "prompt text"');
    console.error('       node llm_gateway.js --claude "prompt text"');
    console.error('       node llm_gateway.js --gemini "prompt text"');
    console.error('       node llm_gateway.js --gemini-api "prompt text"');
    console.error('       node llm_gateway.js --yolo "prompt text"');
    console.error('       node llm_gateway.js --local "prompt text"');
    process.exit(1);
  }

  // Generate correlation ID for this request
  const correlationId = generateCorrelationId();

  try {
    // BUILD PROMPT START
    const CONTRACTS_SIDECAR = process.env.CONTRACTS_SIDECAR || 'contracts.min.json';
    const CONTRACTS_VENDOR = process.env.CONTRACTS_VENDOR || 'codex';
    const CONTRACTS_SLICES = process.env.CONTRACTS_SLICES || 'roles,tools';
    const CONTRACTS_USE_FULL = process.env.CONTRACTS_USE_FULL === '1';
    let contractsBlock = '';
    if (!CONTRACTS_USE_FULL) {
      try {
        contractsBlock = renderSlice({
          vendor: CONTRACTS_VENDOR,
          slice: CONTRACTS_SLICES,
          fmt: 'text',
          sidecar: CONTRACTS_SIDECAR
        });
        if (contractsBlock) {
          contractsBlock = contractsBlock.trim();
        }
      } catch (e) {
        console.warn('[contracts] sidecar render failed, falling back:', e.message);
        contractsBlock = '';
      }
    }

    // RAG Gateway Ownership: Single point of injection with idempotence guard
    const ragQueryEnv = typeof process.env.RAG_USER_PROMPT === 'string' ? process.env.RAG_USER_PROMPT.trim() : '';
    const ragQuery = ragQueryEnv.length > 0 ? ragQueryEnv : prompt;

    // Check for existing RAG injection (idempotence guard)
    if (!/\bRAG Retrieval Plan\b/.test(prompt) && !prompt.replace(/^\s+/, '').startsWith('RAG Retrieval Plan')) {
      // Gateway owns RAG injection with proper guards and telemetry
      prompt = attachRagPlan(prompt, ragQuery, correlationId);

      if (RAG_LOG_SAMPLE_RATE >= 1.0 || Math.random() < RAG_LOG_SAMPLE_RATE) {
        console.error(JSON.stringify({
          event: 'rag.injected',
          correlationId,
          promptLength: prompt.length,
          originalPromptLength: ragQuery.length,
          service: 'llm_gateway'
        }));
      }
    } else {
      if (RAG_LOG_SAMPLE_RATE >= 1.0 || Math.random() < RAG_LOG_SAMPLE_RATE) {
        console.error(JSON.stringify({
          event: 'rag.idempotent_skip',
          correlationId,
          reason: 'already_contains_rag_plan',
          service: 'llm_gateway'
        }));
      }
    }

    if (contractsBlock) {
      prompt = `${contractsBlock}\n\n${prompt}`;
    }
    let response;

    // Hard disable for Phase 2: respect LLM_DISABLED / NEXT_PUBLIC_LLM_DISABLED / WEATHER_DISABLED
    // If any of these flags are truthy, or if none of them are set (default-disabled),
    // short‑circuit without making any LLM calls.
    const flagsPresent = ['LLM_DISABLED','NEXT_PUBLIC_LLM_DISABLED','WEATHER_DISABLED'].some(k => Object.prototype.hasOwnProperty.call(process.env, k));
    const llmDisabled = envFlag('LLM_DISABLED') || envFlag('NEXT_PUBLIC_LLM_DISABLED') || envFlag('WEATHER_DISABLED') || !flagsPresent;
    if (llmDisabled) {
      console.error('LLM disabled via environment; skipping LLM gateway.');
      // Print nothing to stdout so callers treating output as model text get empty string
      process.exit(0);
    }

    if (requestedProfileRaw && requestedProfileRaw !== resolvedProfile && !hasModelOverride) {
      debugLog(`OLLAMA_PROFILE "${requestedProfileRaw}" not recognized; defaulting to "${resolvedProfile}"`);
    }
    if (hasModelOverride) {
      debugLog(`OLLAMA_MODEL overridden via env to "${OLLAMA_MODEL}"`);
    }

    const localDisabledByEnv = envFlag('LLM_GATEWAY_DISABLE_LOCAL');
    const apiDisabledByEnv = envFlag('LLM_GATEWAY_DISABLE_API');
    let skipLocalReason = null;
    if (forceAPI) {
      skipLocalReason = '--api flag';
    } else if (forceClaude) {
      skipLocalReason = '--claude flag';
    } else if (forceGemini) {
      skipLocalReason = '--gemini flag';
    } else if (forceAzureCodex) {
      skipLocalReason = '--azure-codex flag';
    } else if (localDisabledByEnv) {
      skipLocalReason = 'local disabled via env';
    }
    const canUseLocal = !skipLocalReason && !forceClaude;
    const allowFallback = canUseLocal && !forceLocal && !apiDisabledByEnv;
    const fallbackLabel = AZURE_AVAILABLE ? 'Azure' : 'Gemini';

    if (canUseLocal) {
      const routingDetails = [
        `profile=${profileLabel}`,
        `model=${OLLAMA_MODEL}`
      ];
      if (hasModelOverride) {
        routingDetails[routingDetails.length - 1] += ' (env)';
      }
      if (forceLocal) {
        routingDetails.push('forced via --local');
      }
      if (allowFallback) {
        routingDetails.push(`fallback=${fallbackLabel}`);
      }
      console.error(`routing=Local (${routingDetails.join(', ')})`);

      try {
        response = await ollamaComplete(prompt);
        console.error('✅ Local model succeeded');
        console.log(response);
        return;
      } catch (e) {
        console.error('⚠️  Local failed:', e.message);
        debugLog('Local error detail:', e.stack || e.toString());
        if (forceLocal) throw e;
        if (apiDisabledByEnv) {
          throw new Error('API fallback disabled via LLM_GATEWAY_DISABLE_API=1');
        }
        console.error('🔄 Falling back to API...');
      }
    } else {
      const reasons = [];
      if (forceAPI) reasons.push('--api flag');
      if (forceClaude) reasons.push('--claude flag');
      if (forceAzureCodex) reasons.push('--azure-codex flag');
      if (localDisabledByEnv) reasons.push('local disabled via env');
      if (!reasons.length) reasons.push('local unavailable');
      if (apiDisabledByEnv) reasons.push('API disabled via env');
      const apiTarget = forceGemini ? 'Gemini' : (forceClaude ? 'Claude' : (forceMiniMax ? 'MiniMax' : (AZURE_AVAILABLE ? 'Azure' : (ANTHROPIC_AVAILABLE ? 'Claude' : 'Gemini'))));
      console.error(`routing=${apiTarget} (${reasons.join('; ')})`);
      if (apiDisabledByEnv) {
        throw new Error('API usage disabled via LLM_GATEWAY_DISABLE_API=1');
      }
    }

    // Priority: Azure Responses (codex) → Claude → Azure Chat Completions → Gemini
    if (forceAzureCodex) {
      if (!AZURE_CODEX_AVAILABLE && !azureModelOverride) {
        throw new Error('Azure Responses not configured. Set AZURE_OPENAI_DEPLOYMENT_CODEX or AZURE_OPENAI_DEPLOYMENT_CODEX_LIST.');
      }
      response = await azureResponsesComplete(prompt, azureModelOverride);
      console.error('✅ Azure Responses API succeeded');
      console.log(response);
      return;
    }

    if (forceClaude) {
      if (!ANTHROPIC_AVAILABLE) {
        throw new Error('Claude forced but ANTHROPIC_API_KEY not configured');
      }
      response = await anthropicComplete(prompt);
      console.error('✅ Claude API succeeded');
      console.log(response);
      return;
    }

    if (forceGemini) {
      response = await geminiComplete(prompt);
      console.error('✅ Gemini API succeeded');
      console.log(response);
      return;
    }

    if (forceGeminiAPI) {
      response = await geminiComplete(prompt);
      console.error('✅ Gemini API succeeded');
      console.log(response);
      return;
    }

    if (forceMiniMax) {
      if (!MINIMAX_AVAILABLE) {
        throw new Error('MiniMax forced but MINIMAX_API_KEY not configured');
      }
      response = await minimaxComplete(prompt);
      console.error('✅ MiniMax API succeeded');
      console.log(response);
      return;
    }

    if (AZURE_AVAILABLE) {
      response = await azureComplete(prompt);
      console.error('✅ Azure API succeeded');
      console.log(response);
      return;
    }

    if (ANTHROPIC_AVAILABLE) {
      response = await anthropicComplete(prompt);
      console.error('✅ Claude API succeeded');
      console.log(response);
      return;
    }

    response = await geminiComplete(prompt);
    console.error('✅ Gemini API succeeded');
    console.log(response);
    
  } catch (error) {
    console.error('❌ Error:', error.message);
    process.exit(1);
  }
}

async function azureComplete(prompt) {
  const url = new URL(`${AZURE_ENDPOINT}/openai/deployments/${AZURE_DEPLOYMENT}/chat/completions`);
  url.searchParams.set('api-version', AZURE_API_VERSION);

  const payload = {
    messages: [
      { role: 'system', content: 'You are a helpful AI assistant. Always provide complete, substantive responses in JSON format. Wrap your JSON output in ```json``` code blocks if needed for clarity.' },
      { role: 'user', content: prompt }
    ]
    // Removed response_format for GPT-5 reasoning models - let it output naturally
  };

  // For GPT-5 reasoning models, use much higher token limits (reasoning tokens + output tokens)
  const maxTokens = Number.isFinite(AZURE_MAX_TOKENS) && AZURE_MAX_TOKENS > 0 ? AZURE_MAX_TOKENS : 8192;
  if (AZURE_FORCE_COMPLETION) {
    payload.max_completion_tokens = maxTokens;
  } else {
    payload.max_tokens = maxTokens;
  }

  if (AZURE_TEMPERATURE !== null) {
    payload.temperature = AZURE_TEMPERATURE;
  }

  const body = JSON.stringify(payload);

  return new Promise((resolve, reject) => {
    const req = https.request(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'api-key': AZURE_KEY,
        'Content-Length': Buffer.byteLength(body)
      }
    }, res => {
      let data = '';
      res.on('data', chunk => data += chunk);
      res.on('end', () => {
        if (res.statusCode && res.statusCode >= 400) {
          return reject(new Error(`Azure API error ${res.statusCode}: ${data}`));
        }
        try {
          const parsed = JSON.parse(data);
          debugLog('Azure response:', JSON.stringify(parsed, null, 2));
          
          const choice = parsed.choices && parsed.choices[0];
          let content = choice && choice.message && choice.message.content;
          
          // Handle empty content from reasoning models
          if (!content || content.trim() === '') {
            const reasoning = choice && choice.message && choice.message.reasoning;
            if (reasoning && reasoning.trim()) {
              debugLog('Content empty but reasoning present, attempting to extract JSON from reasoning');
              content = reasoning;
            } else {
              const usage = parsed.usage || {};
              const finishReason = choice && choice.finish_reason;
              return reject(new Error(
                `Azure API returned empty content. finish_reason=${finishReason}, ` +
                `reasoning_tokens=${usage.completion_tokens_details?.reasoning_tokens || 0}, ` +
                `completion_tokens=${usage.completion_tokens || 0}, ` +
                `Usage: ${JSON.stringify(usage)}`
              ));
            }
          }
          
          // Extract JSON from markdown code blocks if present
          let extracted = content.trim();
          const jsonBlockMatch = extracted.match(/```json\s*\n([\s\S]*?)\n```/);
          if (jsonBlockMatch) {
            extracted = jsonBlockMatch[1].trim();
          } else {
            // Try to find JSON object in the text
            const jsonMatch = extracted.match(/\{[\s\S]*\}/);
            if (jsonMatch) {
              extracted = jsonMatch[0];
            }
          }
          
          resolve(extracted);
        } catch (err) {
          reject(err);
        }
      });
    });
    req.on('error', reject);
    req.write(body);
    req.end();
  });
}

async function azureResponsesComplete(prompt, modelOverride = '') {
  if (!AZURE_ENDPOINT || !AZURE_KEY) {
    throw new Error('Azure credentials not configured');
  }
  const candidates = [];

  const pushCandidate = (value) => {
    const trimmed = (value || '').trim();
    if (!trimmed) return;
    if (!candidates.includes(trimmed)) {
      candidates.push(trimmed);
    }
  };

  pushCandidate(modelOverride);

  if (AZURE_DEPLOYMENT_CODEX_LIST) {
    AZURE_DEPLOYMENT_CODEX_LIST.split(',')
      .map((s) => s.trim())
      .forEach(pushCandidate);
  }

  pushCandidate(AZURE_DEPLOYMENT_CODEX);
  pushCandidate(AZURE_DEPLOYMENT);

  if (!candidates.length) {
    throw new Error('No Azure Responses deployments configured (set AZURE_OPENAI_DEPLOYMENT_CODEX or AZURE_OPENAI_DEPLOYMENT_CODEX_LIST).');
  }

  const apiVersion =
    process.env.AZURE_OPENAI_RESPONSES_API_VERSION || '2024-10-21-preview';
  let lastError = null;

  for (const deployment of candidates) {
    const url = new URL(
      `${AZURE_ENDPOINT}/openai/deployments/${deployment}/responses`
    );
    url.searchParams.set('api-version', apiVersion);

    const body = {
      input: [
        {
          role: 'user',
          content: [{ type: 'text', text: prompt }],
        },
      ],
    };

    console.error(`🔌 Azure Responses: attempting deployment "${deployment}"`);

    const res = await fetch(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'api-key': AZURE_KEY,
      },
      body: JSON.stringify(body),
    });

    if (!res.ok) {
      const text = await res.text();
      debugLog(`Azure deployment "${deployment}" returned ${res.status}: ${text}`);
      if (res.status === 404) {
        lastError = new Error(
          `Deployment "${deployment}" not found (404). Tried ${candidates.length} candidate(s).`
        );
        continue;
      }
      throw new Error(`Azure Responses API error ${res.status}: ${text}`);
    }

    const json = await res.json();
    debugLog('Azure responses payload:', JSON.stringify(json, null, 2));

    if (json.error) {
      throw new Error(
        `Azure Responses API returned error: ${JSON.stringify(json.error)}`
      );
    }

    const chunks = [];
    const output = Array.isArray(json.output) ? json.output : [];
    for (const message of output) {
      const content = message?.content;
      if (!Array.isArray(content)) continue;
      for (const segment of content) {
        if (segment?.type === 'text' && segment.text) {
          chunks.push(segment.text);
        }
      }
    }

    if (!chunks.length && typeof json.output_text === 'string') {
      chunks.push(json.output_text);
    }

    if (!chunks.length) {
      throw new Error('Azure Responses output contained no text segments');
    }

    console.error(`🔁 Azure Responses: using deployment "${deployment}"`);
    return chunks.join('\n').trim();
  }

  if (lastError) {
    throw lastError;
  }
  throw new Error('Azure Responses API could not find a usable deployment.');
}

async function ollamaComplete(prompt) {
  // RAG removed (Phase 2): send prompt as‑is
  return ollamaCompleteInternal(prompt);
}

function ollamaCompleteInternal(prompt) {
  return new Promise((resolve, reject) => {
    const data = JSON.stringify({
      model: OLLAMA_MODEL,
      prompt: prompt,
      stream: false
    });

    const req = http.request(`${OLLAMA_URL}/api/generate`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Content-Length': Buffer.byteLength(data)
      },
      timeout: 60000
    }, (res) => {
      let body = '';
      res.on('data', chunk => body += chunk);
      res.on('end', () => {
        try {
          let combined = '';
          let done = false;
          for (const line of body.split(/\r?\n/)) {
            if (!line.trim()) continue;
            const json = JSON.parse(line);
            if (typeof json.response === 'string') {
              combined += json.response;
            }
            if (json.done) {
              done = true;
              break;
            }
          }
          if (done && combined.trim().length > 0) {
            resolve(combined);
          } else {
            debugLog('ollama raw response:', body);
            reject(new Error('No response from Ollama'));
          }
        } catch (e) {
          debugLog('ollama parse failure raw:', body);
          reject(new Error('Failed to parse Ollama response'));
        }
      });
    });

    req.on('error', reject);
    req.on('timeout', () => {
      req.destroy();
      reject(new Error('Ollama timeout'));
    });
    req.write(data);
    req.end();
  });
}

function envFlag(name) {
  const raw = (process.env[name] || '').trim().toLowerCase();
  return raw === '1' || raw === 'true' || raw === 'yes' || raw === 'on';
}

function resolveBashExecutable() {
  const candidates = [
    process.env.LLM_GATEWAY_BASH,
    '/bin/bash',
    '/usr/bin/bash',
    'bash'
  ];

  for (const candidate of candidates) {
    if (!candidate) continue;
    const sanitized = stripLeadingControlChars(candidate);
    if (!sanitized) continue;
    if (sanitized.includes(path.sep)) {
      if (fs.existsSync(sanitized)) {
        return sanitized;
      }
      continue;
    }
    return sanitized;
  }

  return 'bash';
}

function stripLeadingControlChars(value) {
  return value.replace(/^[\u0000-\u001F\u007F\uFEFF]+/, '');
}

function shellQuote(args) {
  return args
    .filter(arg => arg !== undefined && arg !== null)
    .map(arg => {
      const str = String(arg);
      if (/^[A-Za-z0-9_:=@%/+.,-]+$/.test(str)) {
        return str;
      }
      const escaped = str.replace(/'/g, "'\\''");
      return `'${escaped}'`;
    })
    .join(' ');
}

function geminiComplete(prompt) {
  return new Promise((resolve, reject) => {
    const args = [prompt];
    if (forceYolo) {
      args.push('--yolo');
    }
    args.push('--output-format', 'json');

    try {
      const result = spawnSync('gemini', args, { encoding: 'utf8' });
      if (result.error || result.status !== 0) {
        throw new Error(result.stderr || 'Failed to run gemini command');
      }
      const json = JSON.parse(result.stdout);
      if (json.response) {
        resolve(json.response);
      } else {
        reject(new Error('No response in gemini command output'));
      }
    } catch (e) {
      reject(new Error(`Failed to run gemini command: ${e.message}`));
    }
  });
}

async function minimaxComplete(prompt) {
  return new Promise((resolve, reject) => {
    const url = `${MINIMAX_BASE_URL}/text/chatcompletion_v2`;
    const data = JSON.stringify({
      model: MINIMAX_MODEL,
      messages: [
        { role: 'user', content: prompt }
      ],
      stream: false,
      temperature: 0.7,
      top_p: 0.95
    });

    const req = https.request(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${MINIMAX_API_KEY}`,
        'Content-Length': Buffer.byteLength(data, 'utf8')
      }
    }, (res) => {
      let body = '';
      res.on('data', chunk => body += chunk);
      res.on('end', () => {
        debugLog('MiniMax status:', res.statusCode);
        debugLog('MiniMax raw body:', body);
        try {
          const json = JSON.parse(body);
          if (json.choices && json.choices[0] && json.choices[0].message && json.choices[0].message.content) {
            resolve(json.choices[0].message.content);
            return;
          }
          if (json.base_resp && json.base_resp.status_msg) {
            const errMsg = json.base_resp.status_msg || 'MiniMax returned error';
            reject(new Error(errMsg));
            return;
          } else {
            reject(new Error('No response from MiniMax'));
          }
        } catch (e) {
          reject(new Error('Failed to parse MiniMax response'));
        }
      });
    });

    req.on('error', reject);
    req.write(data);
    req.end();
  });
}

function anthropicComplete(prompt) {
  return new Promise((resolve, reject) => {
    const url = `${ANTHROPIC_BASE_URL}/v1/messages`;
    const data = JSON.stringify({
      model: ANTHROPIC_MODEL,
      max_tokens: ANTHROPIC_MAX_TOKENS,
      messages: [
        { role: 'user', content: prompt }
      ]
    });

    const req = https.request(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'x-api-key': ANTHROPIC_API_KEY,
        'anthropic-version': ANTHROPIC_VERSION,
        'Content-Length': Buffer.byteLength(data, 'utf8')
      }
    }, (res) => {
      let body = '';
      res.on('data', chunk => body += chunk);
      res.on('end', () => {
        debugLog('Claude status:', res.statusCode);
        debugLog('Claude raw body:', body);
        try {
          const json = JSON.parse(body);
          if (json.content && json.content[0] && json.content[0].text) {
            resolve(json.content[0].text);
            return;
          }
          if (json.error) {
            const errMsg = json.error.message || 'Claude returned error';
            reject(new Error(errMsg));
            return;
          } else {
            reject(new Error('No response from Claude'));
          }
        } catch (e) {
          reject(new Error('Failed to parse Claude response'));
        }
      });
    });

    req.on('error', reject);
    req.write(data);
    req.end();
  });
}

function ragPlanSnippet(question, correlationId) {
  const startTime = Date.now();

  if (!RAG_ENABLED) {
    if (RAG_LOG_SAMPLE_RATE >= 1.0 || Math.random() < RAG_LOG_SAMPLE_RATE) {
      console.error(JSON.stringify({
        event: 'rag.disabled',
        correlationId,
        ragEnabled: RAG_ENABLED,
        ragEnabledRaw: process.env.RAG_ENABLED,
        reason: 'RAG_ENABLED not enabled',
        service: 'llm_gateway'
      }));
    }
    return '';
  }

  if (!fs.existsSync(RAG_HELPER)) {
    if (RAG_LOG_SAMPLE_RATE >= 1.0 || Math.random() < RAG_LOG_SAMPLE_RATE) {
      console.error(JSON.stringify({
        event: 'rag.helper_missing',
        correlationId,
        path: RAG_HELPER,
        service: 'llm_gateway'
      }));
    }
    return '';
  }

  const env = { ...process.env };
  if (!env.PYTHON_BIN) {
    env.PYTHON_BIN = PYTHON_BIN;
  }

  // Set RAG-specific environment variables
  env.RAG_PLAN_LIMIT = String(RAG_TOP_K);
  env.RAG_PLAN_MIN_SCORE = String(RAG_MIN_SCORE);

  const args = ['--repo', REPO_ROOT];

  try {
    const result = spawnSync(RAG_HELPER, args, {
      input: question,
      encoding: 'utf8',
      env,
      timeout: RAG_TIMEOUT_MS
    });

    const duration = Date.now() - startTime;

    if (result.error) {
      const errorMsg = result.error.message || 'Unknown error';
      if (RAG_FAIL_OPEN) {
        if (RAG_LOG_SAMPLE_RATE >= 1.0 || Math.random() < RAG_LOG_SAMPLE_RATE) {
          console.error(JSON.stringify({
            event: 'rag.error',
            correlationId,
            error: errorMsg,
            duration,
            service: 'llm_gateway'
          }));
        }
        return '';
      }
      throw new Error(`RAG helper failed: ${errorMsg}`);
    }

    if (result.status !== 0) {
      const stderr = result.stderr || '';
      if (RAG_FAIL_OPEN) {
        if (RAG_LOG_SAMPLE_RATE >= 1.0 || Math.random() < RAG_LOG_SAMPLE_RATE) {
          console.error(JSON.stringify({
            event: 'rag.error',
            correlationId,
            exitCode: result.status,
            stderr,
            duration,
            service: 'llm_gateway'
          }));
        }
        return '';
      }
      throw new Error(`RAG helper exited with code ${result.status}: ${stderr}`);
    }

    const snippet = (result.stdout || '').trim();
    const snippetLength = snippet.length;

    if (RAG_LOG_SAMPLE_RATE >= 1.0 || Math.random() < RAG_LOG_SAMPLE_RATE) {
      console.error(JSON.stringify({
        event: 'rag.success',
        correlationId,
        snippetLength,
        duration,
        service: 'llm_gateway'
      }));
    }

    return snippet;

  } catch (error) {
    const duration = Date.now() - startTime;
    if (RAG_FAIL_OPEN) {
      if (RAG_LOG_SAMPLE_RATE >= 1.0 || Math.random() < RAG_LOG_SAMPLE_RATE) {
        console.error(JSON.stringify({
          event: 'rag.error',
          correlationId,
          error: error.message,
          duration,
          service: 'llm_gateway'
        }));
      }
      return '';
    }
    throw error;
  }
}

function attachRagPlan(prompt, query, correlationId) {
  // Idempotence guard: Check if RAG has already been injected
  if (/\bRAG Retrieval Plan\b/.test(prompt)) {
    if (RAG_LOG_SAMPLE_RATE >= 1.0 || Math.random() < RAG_LOG_SAMPLE_RATE) {
      console.error(JSON.stringify({
        event: 'rag.idempotent_skip',
        correlationId,
        reason: 'already_injected',
        service: 'llm_gateway'
      }));
    }
    return prompt;
  }
  const trimmed = prompt.replace(/^\s+/, '');
  if (trimmed.startsWith('RAG Retrieval Plan')) {
    if (RAG_LOG_SAMPLE_RATE >= 1.0 || Math.random() < RAG_LOG_SAMPLE_RATE) {
      console.error(JSON.stringify({
        event: 'rag.idempotent_skip',
        correlationId,
        reason: 'starts_with_rag_plan',
        service: 'llm_gateway'
      }));
    }
    return prompt;
  }

  // Call RAG helper to get the snippet
  const snippet = ragPlanSnippet(query ?? prompt, correlationId);
  if (!snippet) {
    return prompt;
  }

  // Enforce max chars limit
  if (snippet.length > RAG_MAX_CHARS) {
    const truncatedSnippet = snippet.substring(0, RAG_MAX_CHARS - 100) + '\n...[truncated]';
    if (RAG_LOG_SAMPLE_RATE >= 1.0 || Math.random() < RAG_LOG_SAMPLE_RATE) {
      console.error(JSON.stringify({
        event: 'rag.truncated',
        correlationId,
        originalLength: snippet.length,
        truncatedLength: truncatedSnippet.length,
        service: 'llm_gateway'
      }));
    }
    return `${truncatedSnippet}\n\n---\n\n${prompt}`;
  }

  // Add provenance marker if enabled
  const provenanceSuffix = RAG_PROVENANCE ? `\n\n<!-- RAG provenance: ${correlationId} -->` : '';

  return `${snippet}${provenanceSuffix}\n\n---\n\n${prompt}`;
}
