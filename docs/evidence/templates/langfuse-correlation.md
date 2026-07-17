# Template: Langfuse correlation

```yaml
run_id: ""
date: ""
request_id: ""
trace_id: ""
model_alias: ""
result: pass|fail|unproven
```

## Expected join

App root trace (`trace_id`) + gateway generation metadata (`request_id` / `trace_id`) both visible in Langfuse project.

## Redacted IDs only

- App trace id:
- Generation / observation id:
- Environment / service / feature / release:

## Screenshot / export

Attach redacted JSON export path (no secrets, no PII prompts):

-
