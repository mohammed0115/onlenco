# Prompt 03 — Speaking and Pronunciation Audit

```text
You are a senior speech assessment engineer and AI product auditor.

Audit the speaking and pronunciation feature honestly.

Do not claim that speaking assessment exists unless the code truly evaluates audio or transcript quality.

Verify:
1. Does the system capture audio?
2. Does it store audio safely?
3. Does it convert speech to text?
4. Does it score pronunciation?
5. Does it score fluency?
6. Does it score grammar from transcript?
7. Does it score vocabulary usage?
8. Does it provide speaking feedback?
9. Does it update StudentLearningProfile?
10. Does it create UserError for speaking mistakes?
11. Does it update UserWeakness?
12. Does AI Tutor support voice input?
13. Does AI Tutor support voice output?
14. Does it handle browser compatibility?
15. Does it handle missing microphone permission?
16. Does it have tests or manual validation scenarios?

Classify current state as one of:
- Not implemented
- Speech-to-text only
- Basic speaking assessment
- Advanced pronunciation scoring

If pronunciation scoring is missing, create a practical roadmap:

MVP:
- browser speech-to-text
- transcript grammar analysis
- AI speaking feedback
- store transcript only
- update weaknesses based on transcript

Improved:
- audio upload
- speech scoring API
- fluency score
- speaking rubric
- structured speaking result model

Advanced:
- phoneme-level pronunciation scoring
- accent-aware feedback
- speaking drills
- pronunciation heatmap
- longitudinal speaking progress

Output:
- Current speaking capability
- Evidence from code
- Missing parts
- Risk level
- Recommended implementation plan
- Tests required
```
