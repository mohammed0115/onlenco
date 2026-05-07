# Prompt 04 — AI Failure Mode Tests

```text
You are a senior AI platform reliability engineer.

Test all AI failure scenarios in Onlenco.

For each AI feature:
- placement
- error analysis
- exercise generation
- AI tutor
- dictionary
- library extraction
- recommendations if AI-assisted
- speaking assessment if AI-assisted

Simulate:
1. Missing API key
2. Invalid API key
3. Timeout
4. Malformed JSON response
5. Empty response
6. Rate limit error
7. Network failure
8. Unexpected exception
9. Very long user input
10. Unsafe or irrelevant AI output

Expected behavior:
- User flow should not crash
- Safe fallback should run
- Error should be logged
- AIUsageLog should be created if implemented
- User should see friendly message
- No raw exception should appear
- Database should remain consistent
- Cost limits should be respected

Tasks:
1. Inspect all AI service files.
2. Identify external API call locations.
3. Confirm try/except and timeout behavior.
4. Confirm JSON validation.
5. Confirm fallback behavior.
6. Add or recommend tests for every failure mode.
7. Confirm no AI failure can break quiz submission, placement result, tutor page, or exercise generation page.

Output:
- AI feature table
- Failure mode coverage table
- Missing fallbacks
- Critical risks
- Tests added or required
- Commands to validate
```
