# T001 — Full Codebase Documentation Restructure

## Metadata

| Field | Value |
|-------|-------|
| Task ID | T001 |
| Title | Full codebase documentation restructure |
| Status | IN_PROGRESS |
| Priority | P0 |
| Created | 2026-04-04 |
| Last Updated | 2026-04-04 |
| Session | S001 |
| Detail File | `docs/03-tasks/tracker/T001-full-docs-restyle.md` |

---

## 1. Goal

Comprehensively review the entire codebase at `sell_manager_CLI`, redesign the `docs/` folder with a numbered prefix structure, and populate it with architecture documentation, session tracker, task tracker, bugs tracker, reference docs, and user guide. Also create a `tmp/` folder for temporary working scripts.

---

## 2. Context

The project lacked structured documentation. The `docs/` folder was nearly empty (only a placeholder SVG). With high context drift risk across sessions, a well-organised documentation system is critical. The user's request was explicit: numbered folders/files, architecture doc, session tracker, task tracker, bug tracker, scripts folder for temp working scripts.

---

## 3. Design Decisions

### 3a. Folder Structure

```
docs/
├── 00-project/          # Charter, goals, glossary, decisions
│   ├── 00-readme.md     # This file — index and principles
│   └── 01-charter.md    # Project charter + glossary
│
├── 01-architecture/     # System design
│   └── 00-architecture-overview.md
│
├── 02-sessions/         # Mandatory per-session log
│   └── 00-session-tracker.md
│
├── 03-tasks/            # Task management
│   ├── 00-task-tracker.md   # Summary index + links (THIS FILE referenced from summary)
│   └── tracker/         # Expanded context per task
│       └── T001-*.md
│
├── 04-bugs/             # Bug and problem tracking
│   ├── 00-bug-tracker.md     # Summary index + links
│   └── tracker/         # Expanded context per bug (future use)
│
├── 05-reference/        # Technical reference
│   ├── 00-reference-index.md
│   ├── 01-config-files.md
│   ├── 02-module-api.md
│   └── 03-runbook.md
│
└── 06-user-guide/       # End-user documentation
    ├── 00-user-guide.md
    └── 01-cli-guide.md
    └── 02-gui-guide.md

tmp/                      # Temporary working scripts (gitignored)
```

**Why numbered prefixes?**
- Git and file explorers sort alphanumerically — numbered folders/files always appear in intended order regardless of rename refactors
- Easy to reference in chat: `docs/03-tasks/00-task-tracker.md` is unambiguous
- Future files slot in between without renames: insert `01a-` or `01b-` as needed

### 3b. Two-Level Task Tracker Design

The task tracker uses two levels:

1. **`docs/03-tasks/00-task-tracker.md`** — Summary index. Table of all tasks with ID, title, status, priority, owner, session, and a one-line summary. Links to expanded detail files.

2. **`docs/03-tasks/tracker/T###-*.md`** — Full task context. Contains goals, design decisions, progress checklist, open questions, related bugs, and any implementation notes.

Rationale: putting all task detail in one file makes it unreadable as the project grows. Splitting forces concise summaries in the index and preserves full context in detail files.

### 3c. Session Tracker

Living append-only document. Newest-first order. Each entry captures:
- Goal for the session
- Context restored (links to previous sessions/tasks)
- Decisions made
- New information learned
- Problems encountered
- Next steps
- Related task and bug IDs

### 3d. Bug Tracker

Two-level design mirroring the task tracker: summary index + optional expanded files for complex bugs.

---

## 4. Progress Checklist

- [x] Explore codebase structure (all 29 Python files read)
- [x] Read existing README.md and docs
- [x] Design and create new docs folder structure (7 folders)
- [x] Create `docs/00-project/00-readme.md`
- [x] Create `docs/00-project/01-charter.md`
- [x] Create `docs/01-architecture/00-architecture-overview.md`
- [x] Create `docs/02-sessions/00-session-tracker.md` with S001
- [x] Create `docs/03-tasks/00-task-tracker.md` (summary index)
- [x] Create `docs/03-tasks/tracker/T001-*.md` (this file)
- [ ] Create `docs/04-bugs/00-bug-tracker.md` + initial bug entries
- [ ] Create `docs/05-reference/` files
- [ ] Create `docs/06-user-guide/` files
- [ ] Create `tmp/README.md` for temporary scripts folder
- [ ] Update `scripts/__init__.py` to document its purpose
- [ ] Verify all files render correctly
- [ ] Update `.gitignore` if needed (docs/ is already gitignored)

---

## 5. Open Questions

- Should `docs/` be tracked in git or remain gitignored? Currently gitignored per `.gitignore`. Consider adding `!docs/00-project/` exceptions if documentation should be versioned.
- Should session/task/bug IDs be sequential integers or use a date-based scheme? Current choice: sequential integers (S001, T001, B001) — simpler to reference in chat.

---

## 6. Related Bugs

- B001: `__main__.py` exceeds 350 lines — single module contains too many responsibilities
- B002: `minute_snapshot.py` exceeds 350 lines — monolithic snapshot function
- B003: Re-entrant queue submission in `ib_worker._poll_positions`
- B004: Inconsistent `dry_run` flag placement across `orders.py` and `order_manager.py`
- B005: `assigned_ma.py` stores `use_rth` setting as `False` — hardcoded False may cause off-hours data gaps
- (Full bug details in `docs/04-bugs/00-bug-tracker.md`)
