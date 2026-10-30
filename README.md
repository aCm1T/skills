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
├── CONTRIBUTING.md
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

## Contribute

- [Contribution guide](CONTRIBUTING.md): steps for preparing and submitting changes.
- [Skill standard](SKILL_STANDARD.md): authoring and publishing requirements, validation commands, and review boundaries.
