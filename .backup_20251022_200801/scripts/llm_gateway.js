#!/usr/bin/env node
/**
 * llm_gateway.js (template) - Local-first LLM tool with API fallback
 * Usage: echo "prompt" | node llm_gateway.js
 *        node llm_gateway.js "prompt text"
 *        node llm_gateway.js --api "prompt text"  (skip local)
 */

const http = require('http');
const https = require('https');
const fs = require('fs');
const path = require('path');

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
      if (semicolonIdx !== -1) val = val.slice(0, semicolonIdx).trim();
      if ((val.startsWith('"') && val.endsWith('"')) || (val.startsWith("'") && val.endsWith("'"))) {
        val = val.slice(1, -1);
      }
      if (!Object.prototype.hasOwnProperty.call(process.env, key)) {
        process.env[key] = val;
      }
    }
  } catch (_) {}
}

loadEnvFrom(path.join(__dirname, '..', '.env.local'));
loadEnvFrom(path.join(process.cwd(), '.env.local'));

// Model profiles
const MODELS = {
  code: 'qwen2.5:14b-instruct-q4_K_M',
  uncensored: 'gpt-oss:20b',
  fast: 'deepseek-coder:6.7b'
};

const requestedProfileRaw = (process.env.OLLAMA_PROFILE || '').trim();
const requestedModelOverride = (process.env.OLLAMA_MODEL || '').trim();
const hasModelOverride = requestedModelOverride.length > 0;
const resolvedProfile = MODELS[requestedProfileRaw] ? requestedProfileRaw : 'code';
const profileLabel = hasModelOverride ? (MODELS[requestedProfileRaw] ? requestedProfileRaw : 'custom') : resolvedProfile;

const OLLAMA_URL = process.env.OLLAMA_URL || 'http://localhost:11434';
const OLLAMA_MODEL = hasModelOverride ? requestedModelOverride : MODELS[resolvedProfile];
const GEMINI_API_KEY = process.env.GEMINI_API_KEY || '';
const GEMINI_MODEL = process.env.GEMINI_MODEL || 'gemini-2.5-flash';
const GEMINI_URL = `https://generativelanguage.googleapis.com/v1beta/models/${GEMINI_MODEL}:generateContent`;

const args = process.argv.slice(2);
const debugEnabled = args.includes('--debug') || args.includes('-d');
const forceAPI = args.includes('--api') || args.includes('-a');
const forceLocal = args.includes('--local') || args.includes('-l');
let prompt = args.filter(a => !a.startsWith('-')).join(' ');
const debugLog = (...m) => { if (debugEnabled) console.error('[debug]', ...m); };

if (!prompt && !process.stdin.isTTY) {
  let stdin = '';
  process.stdin.on('data', c => stdin += c);
  process.stdin.on('end', () => { prompt = stdin.trim(); main(); });
} else {
  main();
}

async function main() {
  if (!prompt) {
    console.error('Usage: echo "prompt" | node llm_gateway.js');
    process.exit(1);
  }
  try {
    let response;

    const localDisabledByEnv = envFlag('LLM_GATEWAY_DISABLE_LOCAL');
    const apiDisabledByEnv = envFlag('LLM_GATEWAY_DISABLE_API');
    const skipLocalReason = forceAPI ? '--api flag' : (localDisabledByEnv ? 'local disabled via env' : null);
    const canUseLocal = !skipLocalReason;

    if (canUseLocal) {
      console.error(`routing=Local (profile=${profileLabel}, model=${OLLAMA_MODEL}${hasModelOverride?' (env)':''})`);
      try {
        response = await ollamaComplete(prompt);
        console.error('✅ Local model succeeded');
        console.log(response);
        return;
      } catch (e) {
        console.error('⚠️  Local failed:', e.message);
        if (forceLocal) throw e;
        if (apiDisabledByEnv) throw new Error('API fallback disabled');
        console.error('🔄 Falling back to API...');
      }
    } else {
      const reasons = [];
      if (forceAPI) reasons.push('--api');
      if (localDisabledByEnv) reasons.push('local disabled');
      console.error(`routing=Gemini (${reasons.join('; ')})`);
      if (apiDisabledByEnv) throw new Error('Gemini usage disabled');
    }

    if (!GEMINI_API_KEY) throw new Error('GEMINI_API_KEY not set');
    response = await geminiComplete(prompt);
    console.error('✅ API succeeded');
    console.log(response);

  } catch (err) {
    console.error('❌ Error:', err.message);
    process.exit(1);
  }
}

async function ollamaComplete(prompt) {
  const fullPrompt = prompt;
  return new Promise((resolve, reject) => {
    const data = JSON.stringify({ model: OLLAMA_MODEL, prompt: fullPrompt, stream: false });
    const req = http.request(`${OLLAMA_URL}/api/generate`, { method: 'POST', headers: { 'Content-Type': 'application/json', 'Content-Length': data.length }, timeout: 60000 }, (res) => {
      let body=''; res.on('data', c=>body+=c); res.on('end', () => {
        try { const json = JSON.parse(body); if (json.response) resolve(json.response); else reject(new Error('No response from Ollama')); }
        catch { reject(new Error('Failed to parse Ollama response')); }
      });
    });
    req.on('error', reject); req.on('timeout', ()=>{req.destroy(); reject(new Error('Ollama timeout'));}); req.write(data); req.end();
  });
}

function geminiComplete(prompt) {
  return new Promise((resolve, reject) => {
    const url = `${GEMINI_URL}?key=${GEMINI_API_KEY}`;
    const data = JSON.stringify({ contents: [{ parts: [{ text: prompt }] }] });
    const req = https.request(url, { method: 'POST', headers: { 'Content-Type': 'application/json', 'Content-Length': Buffer.byteLength(data,'utf8') } }, (res) => {
      let body=''; res.on('data', c=>body+=c); res.on('end', () => {
        try { const json = JSON.parse(body); const t = json.candidates && json.candidates[0]?.content?.parts[0]?.text; if (t) resolve(t); else if (json.error) reject(new Error(json.error.message||'Gemini error')); else reject(new Error('No response from Gemini')); }
        catch { reject(new Error('Failed to parse Gemini response')); }
      });
    });
    req.on('error', reject); req.end(data);
  });
}

function envFlag(name) {
  const raw = (process.env[name] || '').trim().toLowerCase();
  return raw === '1' || raw === 'true' || raw === 'yes' || raw === 'on';
}

