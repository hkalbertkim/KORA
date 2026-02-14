# Reasoning Adapter

v0.1 supports minimal HTTP-backed reasoning adapters. The built-in OpenAI adapter uses `requests` and reads auth from `OPENAI_API_KEY`.

Notes:
- OpenAI calls use the Responses API over HTTPS.
- Adapter outputs are required to be structured JSON and are validated.
- Missing `OPENAI_API_KEY` fails gracefully with a clear adapter error.
