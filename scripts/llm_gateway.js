#!/usr/bin/env node
/**
 * llm_gateway.js - Simple LLM tool: Local first, API fallback
 * Usage: echo "prompt" | node llm_gateway.js
 *        node llm_gateway.js "prompt text"
 *        node llm_gateway.js --api "prompt text"  (skip local)
 */

const http = require('http');
const https = require('https');
const fs = require('fs');
const path = require('path');
const { spawnSync } = require('child_process');

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

loadEnvFrom(path.join(__dirname, '..', '.env.local'));
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
const GEMINI_API_KEY = process.env.GEMINI_API_KEY || '';
const GEMINI_MODEL = process.env.GEMINI_MODEL || 'gemini-2.5-flash';
const GEMINI_URL = `https://generativelanguage.googleapis.com/v1beta/models/${GEMINI_MODEL}:generateContent`;
const AZURE_ENDPOINT = (process.env.AZURE_OPENAI_ENDPOINT || '').replace(/\/$/, '');
const AZURE_KEY = process.env.AZURE_OPENAI_KEY || '';
const AZURE_DEPLOYMENT = process.env.AZURE_OPENAI_DEPLOYMENT || '';
const AZURE_API_VERSION = process.env.AZURE_OPENAI_API_VERSION || '2024-02-15-preview';
const AZURE_AVAILABLE = Boolean(AZURE_ENDPOINT && AZURE_KEY && AZURE_DEPLOYMENT);
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
let prompt = args.filter(a => !a.startsWith('-')).join(' ');
const debugLog = (...messages) => {
  if (debugEnabled) {
    console.error('[debug]', ...messages);
  }
};

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
    process.exit(1);
  }

  try {
    prompt = attachRagPlan(prompt);
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
    const skipLocalReason = forceAPI
      ? '--api flag'
      : (localDisabledByEnv ? 'local disabled via env' : null);
    const canUseLocal = !skipLocalReason;
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
      if (localDisabledByEnv) reasons.push('local disabled via env');
      if (!reasons.length) reasons.push('local unavailable');
      if (apiDisabledByEnv) reasons.push('API disabled via env');
      const apiTarget = AZURE_AVAILABLE ? 'Azure' : 'Gemini';
      console.error(`routing=${apiTarget} (${reasons.join('; ')})`);
      if (apiDisabledByEnv) {
        throw new Error('Gemini usage disabled via LLM_GATEWAY_DISABLE_API=1');
      }
    }

    if (AZURE_AVAILABLE) {
      response = await azureComplete(prompt);
      console.error('✅ Azure API succeeded');
      console.log(response);
      return;
    }

    if (!GEMINI_API_KEY) {
      throw new Error('No API backend configured. Provide Azure or Gemini credentials.');
    }

    response = await geminiComplete(prompt);
    console.error('✅ API succeeded');
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
        'Content-Length': data.length
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
            reject(new Error('No response from Ollama'));
          }
        } catch (e) {
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
    const url = `${GEMINI_URL}?key=${GEMINI_API_KEY}`;
    const data = JSON.stringify({
      contents: [{
        parts: [{ text: prompt }]
      }]
    });

    const req = https.request(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Content-Length': Buffer.byteLength(data, 'utf8')
      }
    }, (res) => {
      let body = '';
      res.on('data', chunk => body += chunk);
      res.on('end', () => {
        debugLog('Gemini status:', res.statusCode);
        debugLog('Gemini raw body:', body);
        try {
          const json = JSON.parse(body);
          if (json.candidates && json.candidates[0]?.content?.parts[0]?.text) {
            resolve(json.candidates[0].content.parts[0].text);
            return;
          }
          if (json.error) {
            const errMsg = json.error.message || 'Gemini returned error';
            reject(new Error(errMsg));
            return;
          } else {
            reject(new Error('No response from Gemini'));
          }
        } catch (e) {
          reject(new Error('Failed to parse Gemini response'));
        }
      });
    });

    req.on('error', reject);
    req.write(data);
    req.end();
  });
}
const REPO_ROOT = path.resolve(__dirname, '..');
const RAG_SCRIPT = path.join(REPO_ROOT, 'scripts', 'rag_plan_snippet.py');
const RAG_DB_PATH = path.join(REPO_ROOT, '.rag', 'index.db');
const PYTHON_BIN = process.env.LLM_GATEWAY_PYTHON || process.env.PYTHON || 'python3';
function ragPlanSnippet(question) {
  if (process.env.LLM_GATEWAY_DISABLE_RAG === '1' || process.env.CODEX_WRAP_DISABLE_RAG === '1') {
    return '';
  }
  if (!fs.existsSync(RAG_DB_PATH) || !fs.existsSync(RAG_SCRIPT)) {
    return '';
  }
  const args = [
    RAG_SCRIPT,
    '--repo',
    REPO_ROOT,
    '--limit',
    process.env.RAG_PLAN_LIMIT || '5',
    '--min-score',
    process.env.RAG_PLAN_MIN_SCORE || '0.4',
    '--min-confidence',
    process.env.RAG_PLAN_MIN_CONFIDENCE || '0.6',
    '--no-log'
  ];
  const result = spawnSync(PYTHON_BIN, args, {
    input: question,
    encoding: 'utf8',
  });
  if (result.error || result.status !== 0) {
    debugLog('ragPlanSnippet error:', result.error || result.stderr);
    return '';
  }
  return (result.stdout || '').trim();
}

function attachRagPlan(prompt) {
  const snippet = ragPlanSnippet(prompt);
  if (!snippet) {
    return prompt;
  }
  return `${snippet}\n\n---\n\n${prompt}`;
}
