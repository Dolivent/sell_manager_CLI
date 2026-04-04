# T019 — Multi-account: CLI client id + GUI ClientIdSelector persistence

## Metadata

| Field | Value |
|-------|-------|
| Task ID | T019 |
| Title | Persist IB client ID in GUI (QSettings); document CLI `--client-id` |
| Status | DONE |
| Session completed | S011 |
| Priority | P3 |
| Created | 2026-04-04 |
| Parent | Spawned from [T015](T015-product-backlog.md) seed: multi-account / sub-account selection |
| Detail File | `docs/03-tasks/tracker/T019-multi-account-client-id.md` |

---

## 1. Goal

CLI already supports `--client-id` (default 1). Expose a dedicated **`ClientIdSelector`** spin box in settings, load/save via **`QSettings`** (`settings_store`).

## 2. Resolution

- `settings_store.get_client_id` / `set_client_id` (`ib/client_id` in QSettings).
- `ClientIdSelector` (`QSpinBox` 1–999999) in `widgets.py`; `SettingsWidget` loads/saves on startup and `valueChanged`.
- **B011:** removed erroneous `self._use_rth = self.use_rth_checkbox.isChecked()` before the checkbox was constructed.
- Tests: `tests/test_settings_store.py`.

## 3. Acceptance

- [x] Delivered
