Fallback local extractor

What this adds
- A conservative, local heuristic fallback for patient registration extraction when OpenAI is unavailable or returns errors.
- Function: `local_extract_registration_fields(text)` in `services/openai_client.py`.
- Normalization: CPF digits-only with checksum validation; date normalized to dd/mm/yyyy; address normalized to "Street Name, number" when detectable.

Behavior
- `extract_registration_fields(text)` will try OpenAI first. If the OpenAI client is not configured or the API call fails, it returns the result of the local heuristic extractor.
- The local extractor is intentionally conservative: fields not confidently detected return `null`.

How to run the local tests
- From the project root run (PowerShell):

  python tests/test_openai_client_local.py

- Or to capture output to a file:

  python tests/test_openai_client_local.py > tests/openai_local_output.log
  type tests\openai_local_output.log

Environment
- To enable OpenAI features set `OPENAI_API_KEY` and optionally `OPENAI_MODEL` in your environment.
- If OpenAI calls fail (429/insufficient_quota etc.) the fallback will be used automatically.

Notes and next steps
- Consider adding metrics/logging to monitor when the fallback is used.
- Consider improving name/address NER or using a small local ML model for better accuracy.

Files of interest
- `services/openai_client.py` — OpenAI wrapper + `local_extract_registration_fields` fallback
- `tests/test_openai_client_local.py` — local extractor examples and quick checks

Contact
- If you want adjustments (address format, stricter CPF rules, different date format), tell me which one and I will update the extractor accordingly.
