# Audit report — sell_manager_CLI

This is an automated, human-readable audit of the `sell_manager_CLI` folder intended to capture risks, implementation status vs PRD, and actionable steps to prepare this project for extraction to a standalone public repository.

---

1) Summary
- Location: `sell_manager_CLI/`
- Main package: `src/sellmanagement`
- Key artifacts: `pyproject.toml`, `README.md`, `PRD_sell_manager_CLI.md`, `config/`, `logs/`, `tests/`
- Status: core functionality implemented (IB connection, downloader, cache, indicators, signal generation). Some safety/operational features missing or partial.

2) Sensitive data & secrets
- No explicit secrets were found by a simple token search, but `logs/` contains runtime data and should be considered sensitive and excluded from a public repo.
- Files to exclude / scrub before making public:
  - `logs/` (contains signals, mid-run snapshots and traces). Remove or replace with sanitized examples.
  - `config/cache/` (contains NDJSON time-series; may include personally-identifying tickers/usage patterns). Replace with empty template or small sample files.

3) Large / binary files
- `config/cache/` contains many `.ndjson` files (one per ticker/timeframe). These will bloat the repo; move to separate storage or remove before publishing.

4) Implementation vs PRD (high level)
- Implemented: IB connect + positions, downloader/backfill, NDJSON cache, MA indicators, minute snapshot, top-of-hour signal generator, JSONL signal audit.
- Partially/missing: async concurrency model (currently batch/sleep), adaptive rate limiter, reconnect manager, idempotency for order placement, full CLI flags, CI/test harness.

5) Files & structure of interest
- `pyproject.toml` — project metadata and dependencies. Verify authors and add license.
- `README.md` — short; expand with usage and CAUTION about live mode.
- `PRD_sell_manager_CLI.md` — design and operational docs (keep; move to `docs/` maybe).
- `src/sellmanagement/` — core code (looks self-contained). Ensure no imports reference parent `dolichart` internals.
- `config/assigned_ma.csv` — source-of-truth config. Keep but sanitize if containing private tickers.

6) Tests
- `tests/` exists with unit tests; run `pytest` after extraction. Some tests may refer to local paths — check and fix fixtures.

7) Immediate actions before extraction (high priority)
- Remove `logs/` from the copy or replace with sanitized sample files. (Reason: may contain private trade/position info.)
- Delete or prune `config/cache/` NDJSON files; keep a tiny example dataset instead.
- Add `.gitignore` to exclude `logs/`, `__pycache__/`, `.venv/`, `config/cache/`, IDE files.
- Add `LICENSE` (choose appropriate license) and update `pyproject.toml` `authors` field.

8) Recommended safe extraction flow (commands)
Run locally (from workspace root) — these are suggestions, do them manually or I can run them if you allow shell commands.

1. Create new repo and commit cleaned copy (no history):
   - Copy folder out of parent (example): `cp -r sell_manager_CLI /path/to/new/repo && cd /path/to/new/repo`
   - Remove logs and cache: `rm -rf logs config/cache`
   - Create `.gitignore` and `LICENSE`
   - `git init && git add . && git commit -m "Initial import of sellmanagement (cleaned)"`

2. If you want to preserve history (recommended for audit), use `git subtree` or `git filter-repo` on the original repo to extract only the `sell_manager_CLI` folder with history. Example (outline):
   - `git subtree split -P sell_manager_CLI -b sell_manager-only`
   - `git clone <new-repo-url>`
   - `cd new-repo && git pull ../path/to/original_repo sell_manager-only`

9) Next steps I will take (if you confirm)
- Produce a `clean-and-export.sh` script that:
  - Removes `logs/` and `config/cache/`
  - Adds `.gitignore` with recommended entries
  - Creates a sanitized `config/assigned_ma.csv` example if needed
  - Optionally extracts git history using `git subtree split` (if you opt-in)
- Run `pytest` and report failing tests (if you want me to run tests locally).

---

Appendix: quick findings from code & logs
- `logs/signals.jsonl` contains repeated simulated signals (fine). Contains no obvious API keys by regex scan.
- `pyproject.toml` lists `ib_insync`, `pandas`, `numpy` as dependencies.
- `config/cache/` contains many `.ndjson` files which will create a very large repository if included.

If you'd like, I can now (pick one):
- A) create `clean-and-export.sh` and `/.gitignore` and add them here, or
- B) run the history-extraction commands to produce a new git branch with only `sell_manager_CLI` history, or
- C) produce a sanitized snapshot (copy) of the folder ready to be committed as a new public repo.

Signed-off-by: automated-audit-bot


