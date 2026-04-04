# T012 — Pytest and dev tooling

## Metadata

| Field | Value |
|-------|-------|
| Task ID | T012 |
| Title | Optional dev dependencies and pytest adoption |
| Status | DONE |
| Priority | P3 |
| Session completed | S007 |
| Detail File | `docs/03-tasks/tracker/T012-pytest-dev.md` |

---

## 1. Resolution (S007)

- `pyproject.toml` `[project.optional-dependencies] dev` includes `pytest>=7.4`.
- CI runs `pytest tests -q` after `unittest` (same test modules; both green).

---

## 2. Follow-up (optional)

- Ruff/mypy in `dev`
- Pure pytest style / fixtures for less boilerplate
