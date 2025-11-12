# Azure OpenAI – East US 2 Availability & Pricing (updated 2025-11-05)

**Source**: `~/Downloads/Azure East Pricing.ods` (converted to CSV on 2025-11-04). Figures are per 1M tokens unless stated otherwise. Prices are in USD.  
**Access note**: Azure lists *GPT-5 Pro* and other premium SKUs as available in East US 2, but procurement still routes through an account rep. Treat the figures below as guidance and expect enterprise quoting for final numbers.

## Quick highlights
- GPT-5 base models bill at $1.25 input / $10 output per 1M tokens globally, while the Pro tier jumps to $15 / $120. Mini and Nano tiers provide sizeable cost reductions.
- GPT-4.1 and GPT-4o remain the “workhorse” options: $2 input / $8 output for GPT-4.1 global, and $2.50 / $10 for GPT-4o (2024-11-20 release).
- Reasoning (o-series) models sit between GPT-4.1 and GPT-5 in price. o3 global is $2 input / $8 output; o1 global is $15 / $60.
- Realtime/audio SKUs introduce separate text vs. audio token pricing—for example GPT-4o Realtime global charges $5 text input vs. $40 audio input.
- Provisioned throughput starts at 15 PTUs per deployment for most global SKUs at $1/hour, with monthly reservations at $260 and yearly at $2,652.

## Limited / request-only SKUs

| Model family | Notes |
| --- | --- |
| **GPT-5 Pro / GPT-5 / GPT-5 Codex** | High-performance reasoning and code-generation models. Listed in East US 2 but require Microsoft account rep approval before enablement. Expect enterprise contracting; not self-service. |
| **GPT-Image-1 / GPT-Image-1-mini** | Multimodal image generation; Azure labels current launch as limited preview. Request access via Azure AI Foundry preview form. |
| **Computer-use-preview** | Enables Responses API agents to control desktop interfaces. Available by request only; usage bills at $3 input / $12 output per 1M tokens once enabled. |
| **Sora (OpenAI)** | Text/image/video-to-video generation. Azure currently offers in East US 2 and Sweden Central under controlled preview; requires sales engagement and compliance review. |
| **o3-pro, o1, o1-preview, broader o-series** | Advanced reasoning / agentic workflows. Azure shows SKUs in the pricing sheet, but many tenants need to file a request to unlock them (especially o1/o3 variants). |

## GPT-5 family (per 1M tokens)

| Model | Scope | Input | Cached Input | Output |
| --- | --- | --- | --- | --- |
| GPT-5 2025-08-07 | Global | $1.25 | $0.13 | $10 |
| GPT-5 2025-08-07 | Data Zone (US/EU) | $1.38 | $0.14 | $11 |
| GPT-5 Pro | Global | $15.00 | — | $120 |
| GPT-5 Codex | Global | $1.25 | $0.13 | $10 |
| GPT-5 Chat | Global | $1.25 | $0.13 | $10 |
| GPT-5-mini | Global | $0.25 | $0.03 | $2.00 |
| GPT-5-mini | Data Zone | $0.28 | $0.03 | $2.20 |
| GPT-5-nano | Global | $0.05 | $0.01 | $0.40 |
| GPT-5-nano | Data Zone | $0.06 | $0.01 | $0.44 |

> **Sales assist**: GPT-5 Pro and Codex tiers may require an Enterprise agreement to activate despite the published rates.

## GPT-4.5 and GPT-4.1 family (per 1M tokens)

| Model | Scope | Input | Cached Input | Output | Batch Input | Batch Output |
| --- | --- | --- | --- | --- | --- | --- |
| GPT-4.5 Preview (2025-02-27) | Global | $75.00 | $37.50 | $150 | — | — |
| GPT-4.1 (2025-04-14) | Global | $2.00 | $0.50 | $8.00 | $1.00 | $4.00 |
|  | Data Zone | $2.20 | $0.55 | $8.80 | $1.10 | $4.40 |
|  | Regional | $2.20 | $0.55 | $8.80 | — | — |
| GPT-4.1 Mini | Global | $0.40 | $0.10 | $1.60 | $0.20 | $0.80 |
|  | Data Zone | $0.44 | $0.11 | $1.76 | $0.22 | $0.88 |
|  | Regional | $0.44 | $0.11 | $1.76 | — | — |
| GPT-4.1 Nano | Global | $0.10 | $0.03 | $0.40 | $0.05 | $0.20 |
|  | Data Zone | $0.11 | $0.03 | $0.44 | $0.06 | $0.22 |
|  | Regional | $0.11 | $0.03 | $0.44 | — | — |

## GPT-4o releases

| Release | Scope | Input | Cached Input | Output | Batch Input | Batch Output |
| --- | --- | --- | --- | --- | --- | --- |
| GPT-4o (2024-11-20) | Global | $2.50 | $1.25 | $10.00 | $1.25 | $5.00 |
|  | Data Zone | $2.75 | $1.375 | $11.00 | — | — |
|  | Regional | $2.75 | $1.375 | $11.00 | — | — |
| GPT-4o (2024-08-06) | Global | $2.50 | $1.25 | $10.00 | $1.25 | $5.00 |
|  | Data Zone | $2.75 | $1.375 | $11.00 | $1.375 | $5.50 |
|  | Regional | $2.75 | $1.375 | $11.00 | — | — |
| GPT-4o (2024-05-13) | Global | $5.00 | — | $15.00 | — | — |
|  | Data Zone | $5.50 | — | $16.50 | — | — |
|  | Regional | $5.50 | — | $16.50 | — | — |
| GPT-4o Mini (2024-07-18) | Global | $0.15 | $0.075 | $0.60 | $0.075 | $0.30 |
|  | Data Zone | $0.165 | $0.083 | $0.66 | — | — |
|  | Regional | $0.165 | $0.083 | $0.66 | — | — |

## Reasoning (o-series) models

| Model | Scope | Input | Cached Input | Output | Batch Input | Batch Output |
| --- | --- | --- | --- | --- | --- | --- |
| o3 (2025-04-16) | Global | $2.00 | $0.50 | $8.00 | $1.00 | $4.00 |
|  | Data Zone | $2.20 | $0.55 | $8.80 | $1.10 | $4.40 |
|  | Regional | $2.20 | $0.55 | $8.80 | — | — |
| o4-mini (2025-04-16) | Global | $1.10 | $0.28 | $4.40 | $0.55 | $2.20 |
|  | Data Zone | $1.21 | $0.31 | $4.84 | $0.61 | $2.42 |
|  | Regional | $1.21 | N/A | $4.84 | — | — |
| o3 mini (2025-01-31) | Global | $1.10 | $0.55 | $4.40 | $0.55 | $2.20 |
|  | Data Zone | $1.21 | $0.605 | $4.84 | $0.605 | $2.42 |
|  | Regional | $1.21 | $0.605 | $4.84 | — | — |
| o1 (2024-12-17) | Global | $15.00 | $7.50 | $60.00 | — | — |
|  | Data Zone | $16.50 | $8.25 | $66.00 | — | — |
|  | Regional | $16.50 | $8.25 | $66.00 | — | — |
| o1 Mini (2024-09-12) | Global | $1.10 | $0.55 | $4.40 | — | — |
|  | Data Zone | $1.21 | $0.605 | $4.84 | — | — |
|  | Regional | $1.21 | $0.605 | $4.84 | — | — |

## Specialized services

- **Deep Research (o3 deep research)**: $10 input / $2.50 cached / $40 output per 1M tokens (global). Azure also bills separately for Bing grounding queries.
- **Sora video generation**:
  - Sora 2 Global: $0.10 per rendered second (720x1280 portrait or 1280x720 landscape).
  - Sora 2 Pro Global: $0.30 per second (same resolutions).
  - Sora 2 Pro High-Res Global: $0.50 per second (1024x1792 or 1792x1024).
- **GPT-Image-1**:
  - Mini Global: Input text $2, input image $2.50, output image $8.
  - Standard Global: Input text $5, input image $10, output image $40.
  - Regional/Data Zone SKUs: Input text $5.50, input image $11, output image $44.

## Audio & realtime models

- **GPT-realtime (global)**  
  - Text: $4 input / $0.40 cached / $16 output  
  - Audio: $32 input / $0.40 cached / $64 output  
  - Image: $5 input / $0.50 cached (no output charge)
- **GPT-realtime-mini (global)**  
  - Text: $0.60 input / $0.06 cached / $2.40 output  
  - Audio: $10 input / $0.30 cached / $20 output  
  - Image: $0.80 input / $0.08 cached
- **GPT-audio (global)**  
  - Text: $2.50 input / $10 output  
  - Audio: $40 input / $80 output
- **GPT-audio mini (global)**  
  - Text: $0.60 input / $2.40 output  
  - Audio: $10 input / $20 output
- **GPT-4o Transcribe**  
  - Text: $2.50 input / $10 output; Audio: $6 input (no audio output fee published)
- **GPT-4o Mini Transcribe**  
  - Text: $1.25 input / $5 output; Audio: $3 input
- **GPT-4o Mini TTS**  
  - Text: $0.60 input; Audio output $12
- **Realtime API (2024-12-17 releases)**  
  - GPT-4o Realtime global: Text $5 input / $2.50 cached / $20 output; Audio $40 input / $2.50 cached / $80 output.  
  - GPT-4o Mini Realtime global: Text $0.60 input / $0.30 cached / $2.40 output; Audio $10 input / $0.30 cached / $20 output.  
  - Data Zone variants add ~10% surcharge (e.g., GPT-4o Realtime text input $5.50, audio input $44).
- **Chat Completions Audio Preview (2024-12-17)** mirrors the realtime numbers but for async usage: GPT-4o audio preview text $2.50 input / $10 output; audio $40/$80. The mini variant scales to $0.15/$0.60 text and $10/$20 audio.

## Built-in tools & agents

- Computer-use tool (Responses API only): $3 input / $12 output per 1M tokens.  
- File Search tool call: $2.50 per 1K tool calls; vector storage $0.11 per GB per day (first GB free).  
- Code Interpreter: $0.033 per session (up to 1 hour).  
- Computer-Using Agent (preview): same $3 input / $12 output pricing as the tool call.

## Provisioned throughput (PTU) pricing

| Deployment | Min PTUs | Hourly | Monthly reservation | Yearly reservation |
| --- | --- | --- | --- | --- |
| GPT-5 (Global) | 15 | $1.00 | $260 | $2,652 |
| GPT-5 (Data Zone) | 15 | $1.10 | $286 | $2,916 |
| GPT-5 (Regional) | 50 | $2.00 | $286 | $2,916 |
| GPT-4.1 / GPT-4o / o3 / o4-mini (Global) | 15 | $1.00 | $260 | $2,652 |
| GPT-4.1 / GPT-4o / o3 / o4-mini (Data Zone) | 15 | $1.10 | $286 | $2,916 |
| GPT-4.1 / GPT-4o / o3 / o4-mini (Regional) | 25–50 | $2.00 | $286 | $2,916 |
| Fine-tuned GPT-4o (Regional) | 50 | $2.00 | $286 | $2,916 |
| GPT-4o Mini (Global) | 15 | $1.00 | $260 | $2,652 |
| GPT-4o Mini (Regional or FT) | 25 | $2.00 | $286 | $2,916 |

> Monthly and yearly reservation prices are the Azure retail figures; negotiated enterprise discounts may apply.

## Fine-tuning price points

- **o4-mini (reinforcement fine-tuning)**  
  - Global: $1.10 input / $4.40 output per 1M tokens, training $100/hour, hosting $1.70/hour.  
  - Regional: $1.21 input / $4.84 output, training $110/hour, hosting $1.70/hour.  
  - Grader usage: GPT-4o grader $2.75 input / $11 output; o3-mini grader $1.21 input / $4.84 output (cached rates reduced by ~50%).
- **GPT-4.1 (developer/global)**  
  - $2.00 input / $0.50 cached / $8.00 output per 1M tokens; training $25/1M tokens; hosting $1.70/hour.
- **GPT-4.1 mini**  
  - Regional: $0.44 input / $0.11 cached / $1.76 output; training $5.50/1M tokens; hosting $1.70/hour.

## Gaps & follow-ups

- Azure shows **GPT-5 Pro** and certain enterprise SKUs without self-serve enablement; coordinate with your Microsoft rep before committing workloads.
- Token pricing excludes ancillary charges (grounding with Bing, storage, networking).
- Revisit this sheet whenever Microsoft issues quarterly price updates or new regional launches.
