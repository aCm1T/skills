# Skills

A small, curated collection of reusable agent skills. Each skill is self-contained and keeps its detailed workflow and supporting references alongside its `SKILL.md`.

## Available skills

| Skill | What it does | Location |
| --- | --- | --- |
| [作业完成与核验 (`complete-coursework`)](complete-coursework/SKILL.md) | Completes, revises, and checks coursework deliverables while preserving essential reasoning and honest validation. | [`complete-coursework/`](complete-coursework/) |
| [Blackboard 课件下载 (`blackboard-downloader`)](blackboard-downloader/SKILL.md) | Downloads specified course attachments, preserves course folders, and verifies files using a shared local runtime. | [`blackboard-downloader/`](blackboard-downloader/) |
| [考试 CP 制作 (`create-cheat-sheet`)](create-cheat-sheet/SKILL.md) | Builds lecture-ordered exam cheat sheets from course materials, with a verified printable PDF and editable source. | [`create-cheat-sheet/`](create-cheat-sheet/) |

## Use a skill

Copy the desired skill folder into a directory your agent scans for skills. For Codex, the usual personal location is `~/.codex/skills/`:

```text
~/.codex/skills/complete-coursework/SKILL.md
```

Some setups use a workspace-local skills directory instead. Follow the instructions for your agent and restart or refresh it if needed.

You can also download a ZIP from the repository's **Code → Download ZIP** menu and copy the selected skill folder from the archive.

## Repository layout

```text
.
├── README.md
├── SKILL_STANDARD.md
├── CI/
│   ├── requirements.txt
│   ├── validate_skills.py
│   └── tests/
├── blackboard-downloader/
│   ├── SKILL.md
│   ├── agents/
│   └── references/
├── complete-coursework/
│   ├── SKILL.md
│   ├── agents/
│   ├── references/
│   └── scripts/
└── create-cheat-sheet/
    ├── SKILL.md
    ├── agents/
    ├── references/
    └── assets/
```

Each skill has its own top-level directory. `CI/` holds repository validation tools, tests, and dependencies. A skill may include a `SKILL.md`, optional UI metadata under `agents/`, supporting material under `references/`, and helper scripts under `scripts/`.

## Add or update a skill

Follow [the skill standard](SKILL_STANDARD.md) and [contribution guide](CONTRIBUTING.md). The standard distinguishes automatic checks from human review; it does not require identical section headings.

1. Give the skill its own top-level directory and a concise, descriptive name.
2. Keep `SKILL.md` focused on when to use the skill and the core workflow; move detailed procedures into linked references.
3. Include only generic, reusable guidance. Remove personal names, account or student identifiers, specific private course material, machine paths, credentials, private chat excerpts, and identifying metadata.
4. Check that every referenced file exists and that the instructions match the included files.
5. Run the relevant structural checks and test helper scripts with representative valid and invalid inputs.
6. Review the final diff and the full archive or release contents before publishing.
7. Update the table above when adding a skill.

## Privacy

This is a public repository. Treat every committed file, filename, metadata field, example, and script output as public. Do not add private source assignments, chat exports, personal records, credentials, or machine-specific paths.

## Validate changes

Use Python 3.10 or later, preferably in a virtual environment:

```sh
python -m pip install -r CI/requirements.txt
python CI/validate_skills.py
python -m unittest discover -s CI/tests -v
```

The checker examines all skills and Git-tracked files, so stage intended new files before running it. GitHub Actions runs the same checks on pushes and pull requests. Tests use temporary synthetic files and do not log into Blackboard or use private coursework.

CI covers structure, file links, Python syntax and selected privacy risks. It does not establish factual correctness, complete privacy review, or task success. See [automatic checks and human review](SKILL_STANDARD.md#9-自动检查与人工审阅) for limitations and instructions for making checks required before merging.
