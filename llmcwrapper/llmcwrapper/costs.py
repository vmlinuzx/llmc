# llmcwrapper/costs.py
# Configurable per-provider/model pricing (USD per 1K tokens). Defaults are 0.0 to avoid surprises.
# Override via user/project config under [pricing.<provider>.<model>].
DEFAULT_PRICING = {
    "anthropic": {},
    "minimax": {}
}

def estimate_cost(provider, model, input_tokens, output_tokens, pricing):
    prov = (pricing or {}).get(provider, {}) or DEFAULT_PRICING.get(provider, {})
    model_pr = prov.get(model, {})
    in_p = model_pr.get("prompt", 0.0)
    out_p = model_pr.get("completion", 0.0)
    return (input_tokens or 0) / 1000.0 * in_p + (output_tokens or 0) / 1000.0 * out_p
