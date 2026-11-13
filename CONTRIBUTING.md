# Contributing to guardscore

Thank you for helping make this benchmark more useful. This guide explains how to add a new incident case.

## What makes a good incident

A good incident is a real event where an AI coding agent took a destructive or irreversible action. The ideal case:

- Comes from a public, findable source (a news article, a postmortem, a forum thread, an official bulletin).
- Describes an action that most guards should catch, such as deleting production data, wiping files, or making destructive cloud API calls.
- Has enough detail to write a realistic action field, even if the exact command must be reconstructed.

If you have read about an incident and want to add it, check first that it is not already in the cases/incidents/ folder.

## How to add an incident case

1. Find a reliable public source. Open the URL and confirm the details yourself. Do not write a case from memory or from a summary you have not verified.

2. Create a TOML file in cases/incidents/. The file name must be lowercase letters, digits, and hyphens, with a .toml extension. The id field inside the file must match the file name.

3. Fill in every required field. The full field reference is in docs/case-format.md.

4. Set reconstructed = true in the action section unless the exact text of the action appears verbatim in a source. If the source only describes what happened, reconstruct a generic version using api.example.com as a hostname and REDACTED for any secret values.

5. Run python -m guardscore validate to check your case before opening a pull request. All cases must pass with zero errors.

## Rules for sources

- Use at least one HTTPS URL.
- Prefer the original report (the people involved posted about it) over a news article, and a news article over a secondhand summary. Set the reliability field to match.
- Use the date the event happened, not the date the article was published. If only the month is known, use YYYY-MM.

## Rules for writing

- No real secrets anywhere. Use REDACTED for tokens, passwords, and API keys.
- No em dashes or en dashes in any file, comment, or commit message. Use commas, periods, or colons instead.
- Use plain, friendly sentences. Keep paragraphs short.
- Do not copy sentences from your sources. Paraphrase in your own words. You may quote a few words if they are distinctive.
- Do not invent details. If the source does not say what the exact command was, set reconstructed = true and write a plausible generic version.

## Everyday cases

Everyday cases represent safe, routine commands that a guard should let through without blocking. If you want to add one, make sure it has expected = "allow", kind = "everyday", and the tag "everyday". Everyday cases need no source section.

## Running the checks locally

```
pip install -e ".[dev]"
python -m guardscore validate
pytest
```

Both must pass before you open a pull request.
