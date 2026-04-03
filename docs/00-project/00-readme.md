# Project Documentation — sell_manager_CLI

> **Session / context note:** This project suffers from high context drift risk.  
> Every significant work session must be logged in `docs/02-sessions/`.  
> Every task and sub-task goes into `docs/03-tasks/tracker/`.  
> Every bug, regression suspicion, or design problem goes into `docs/04-bugs/`.

---

## Folder Index

| # | Folder | Purpose |
|---|--------|---------|
| `00-project/` | Project | Project charter, goals, non-goals, and key decisions |
| `01-architecture/` | Architecture | System design, data flow, module responsibilities |
| `02-sessions/` | Sessions | Session-by-session work log (required for every session) |
| `03-tasks/` | Tasks | Task tracker + expanded-context detail files |
| `04-bugs/` | Bugs | Bug reports, regression log, problem investigations |
| `05-reference/` | Reference | Config file formats, API surface, runbook |
| `06-user-guide/` | User Guide | End-user walkthrough (setup, CLI, GUI, troubleshooting) |

---

## Key Principles

1. **Numbered prefixes** on every folder and file create stable, order-stable references that survive renames.
2. **Tracker detail separation**: expanded task context lives in `03-tasks/tracker/`; the main task tracker only holds summaries + links. This prevents the tracker from becoming unreadable while preserving full context.
3. **Session logging is mandatory** — each entry captures the session's goal, decisions made, blockers, and next steps. This is the project's only defence against context drift across sessions.
4. **Bug entries are timestamped and tagged** by component — never delete old entries; they serve as regression history.
5. **Reference docs are versioned** alongside the code; if a config format changes, the reference doc is updated in the same commit.

---

## Quick Links

- Current task: [`docs/03-tasks/00-task-tracker.md`](03-tasks/00-task-tracker.md)
- Session log: [`docs/02-sessions/`](02-sessions/)
- Bugs & problems: [`docs/04-bugs/00-bug-tracker.md`](04-bugs/00-bug-tracker.md)
- Architecture: [`docs/01-architecture/`](01-architecture/)
- User guide: [`docs/06-user-guide/00-user-guide.md`](06-user-guide/00-user-guide.md)
