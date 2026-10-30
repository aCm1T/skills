# Contributing

Contributions should add or improve reusable skills while keeping this repository safe to publish publicly.

Follow [SKILL_STANDARD.md](SKILL_STANDARD.md), the source of truth for repository conventions. Different skills may use different section headings and optional resource directories.

Before opening a change:

- Keep each skill in a separate top-level directory.
- Keep the main `SKILL.md` concise and link supporting references with relative paths.
- Remove personal details, private coursework, chat transcripts, credentials, and machine-specific paths from all files and metadata.
- Verify links, declared files, and helper scripts; test both expected success and failure cases where practical.
- Inspect the complete diff and any generated archive for accidental private content.
- Update the root README skill index.
- Stage intended files, install `requirements-ci.txt`, run `python scripts/validate_skills.py` and `python -m unittest discover -s tests -v` before pushing. CI uses these same commands.

Automated checks do not replace review of task scope, consent, external interfaces, licenses, private context, and the accuracy of completion claims. Keep public service URLs and generic authentication examples when useful; never include working credentials. Document narrow scanner false positives with a line fingerprint and reason as specified in the standard.

Do not include user-specific source documents or completed assignments in this repository.
