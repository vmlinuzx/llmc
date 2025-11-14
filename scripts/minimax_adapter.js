#!/usr/bin/env node
/**
 * MiniMax -> Anthropic API Adapter
 * Translates Anthropic Messages API format to MiniMax's native format
 */

const http = require('http');
const https = require('https');

const MINIMAX_URL = 'https://api.minimax.io/v1/text/chatcompletion_v2';
const MINIMAX_TOKEN = process.env.MINIMAX_API_KEY;
const PORT = process.env.PORT || 8080;

if (!MINIMAX_TOKEN) {
  console.error('Error: MINIMAX_API_KEY environment variable not set');
  process.exit(1);
}

function translateRequest(anthropicRequest) {
  // Anthropic -> MiniMax format
  return {
    model: 'minimax-m2',
    messages: anthropicRequest.messages.map(msg => ({
      role: msg.role,
      content: msg.content
    }))
  };
}

function translateResponse(minimaxResponse) {
  // MiniMax -> Anthropic format
  const choice = minimaxResponse.choices[0];
  return {
    id: minimaxResponse.id,
    type: 'message',
    role: 'assistant',
    content: [{
      type: 'text',
      text: choice.message.content
    }],
    model: minimaxResponse.model,
    stop_reason: choice.finish_reason === 'stop' ? 'end_turn' : choice.finish_reason,
    usage: {
      input_tokens: minimaxResponse.usage.prompt_tokens,
      output_tokens: minimaxResponse.usage.completion_tokens
    }
  };
}

const server = http.createServer(async (req, res) => {
  // CORS headers
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'POST, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type, x-api-key, anthropic-version');
  
  if (req.method === 'OPTIONS') {
    res.writeHead(200);
    res.end();
    return;
  }

  if (req.method !== 'POST' || req.url !== '/v1/messages') {
    res.writeHead(404, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({ error: 'Not found' }));
    return;
  }

  let body = '';
  req.on('data', chunk => body += chunk);
  req.on('end', () => {
    try {
      const anthropicReq = JSON.parse(body);
      const minimaxReq = translateRequest(anthropicReq);

      const postData = JSON.stringify(minimaxReq);
      const options = {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${MINIMAX_TOKEN}`,
          'Content-Length': Buffer.byteLength(postData)
        }
      };

      const minimaxRequest = https.request(MINIMAX_URL, options, (minimaxRes) => {
        let responseData = '';
        minimaxRes.on('data', chunk => responseData += chunk);
        minimaxRes.on('end', () => {
          try {
            const minimaxResponse = JSON.parse(responseData);
            const anthropicResponse = translateResponse(minimaxResponse);
            
            res.writeHead(200, { 'Content-Type': 'application/json' });
            res.end(JSON.stringify(anthropicResponse));
          } catch (err) {
            console.error('Response translation error:', err);
            res.writeHead(500, { 'Content-Type': 'application/json' });
            res.end(JSON.stringify({ error: 'Translation error', details: err.message }));
          }
        });
      });

      minimaxRequest.on('error', (err) => {
        console.error('MiniMax API error:', err);
        res.writeHead(500, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ error: 'MiniMax API error', details: err.message }));
      });

      minimaxRequest.write(postData);
      minimaxRequest.end();
      
    } catch (err) {
      console.error('Request parsing error:', err);
      res.writeHead(400, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ error: 'Bad request', details: err.message }));
    }
  });
});

server.listen(PORT, '127.0.0.1', () => {
  console.log(`🚀 MiniMax->Anthropic adapter running on http://127.0.0.1:${PORT}`);
  console.log(`Configure Claude Code with: export ANTHROPIC_BASE_URL="http://127.0.0.1:${PORT}"`);
});
