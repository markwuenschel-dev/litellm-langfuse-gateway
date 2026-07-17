# Template: provider smoke

```yaml
run_id: ""
date: ""
alias: ""           # e.g. openai-general
provider_route: ""  # e.g. openai/gpt-4o-mini
virtual_key_alias: ""  # not the secret
LLG_LIVE: "1"
result: pass|fail|unproven
```

## Command (redact secrets)

```bash
export LLG_LIVE=1
export LITELLM_BASE_URL=http://localhost:4000/v1
export LITELLM_VIRTUAL_KEY=***REDACTED***
uv run llg smoke --alias <alias>
```

## Response (redacted)

- HTTP status:
- `id` / model echoed:
- Token usage (if present):
- Latency:

## Spend / Langfuse

- LiteLLM spend visible: yes/no (no key material)
- Langfuse observation id (if any):

## Notes

-
