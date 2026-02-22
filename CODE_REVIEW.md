# Code Review Action Plan

Generated from a full codebase review. Items are grouped by severity and tracked below.

---

## Critical

- [ ] **Duplicate `_workspace_cwd()` context manager** — identical definition in `setup_flow.py`, `deploy_mech_cmd.py`, `run_cmd.py`, `stop_cmd.py`. Extract to shared module.
- [ ] **Duplicate `SUPPORTED_CHAINS` constant** — identical tuple defined in the same 4 files. Extract to shared constants module.
- [ ] **`deploy_mech_cmd` missing `require_initialized()` guard** — every other command checks for an initialised workspace; this one doesn't, leading to confusing downstream failures.

---

## High

- [ ] **Inconsistent error handling in `update_onchain.py`** — `_load_env()` raises, `_fetch_metadata_hash()` returns silently, `_send_safe_tx()` wraps as `RuntimeError`. Establish a consistent strategy.
- [ ] **128-line `_validate_metadata_file()` in `publish.py`** — 5+ levels of nesting, untestable in parts. Break into focused helper functions (`_validate_metadata_structure`, `_validate_tool_metadata`, `_validate_output_schema`, etc.).
- [ ] **`add_tool_cmd.py` uses raw `Path(__file__).parent` for templates** — should use `importlib.resources` as already done in `resources.py`.
- [ ] **`update_service_after_deploy()` ignores return value** — `service.update_env_variables_values()` result is never checked; silent failures possible.

---

## Missing Tests

- [ ] **`workspace.py`** — `initialize_workspace()` has no direct unit tests (only mocked in CLI tests). Add tests for happy path, force flag, and package directory copying edge cases.
- [ ] **`setup_flow.py` private functions** — `_deploy_mech`, `_create_private_key_files`, `_setup_private_keys` only appear as mocks. Add direct tests including "already deployed" path and key file edge cases.
- [ ] **`publish.py` `_validate_metadata_file()`** — only happy path covered. Add tests for invalid JSON, missing keys, type mismatches, malformed nested structures.
- [ ] **`run_cmd.py` `_get_latest_service_hash()`** — missing test cases: `packages.json` not found, hash not in packages, autonomy command failure.
- [ ] **`add_tool_cmd.py` `generate_tool_file()`** — only tested through mocks. Add direct tests for template substitution, file writing, `__init__` cascading.
- [ ] **`setup_flow.py` `_normalize_nullable_env_vars()`** — only happy path tested. Add tests for missing required vars and already-set values.

---

## Minor

- [ ] **`context.py` `resolve_workspace_path()`** — thin wrapper around `get_default_workspace()` with no added logic. Consider removing.
- [ ] **Logging inconsistency in `deploy_mech.py`** — `logger` used only for warnings; everything else uses `click.echo()`. Pick one.
- [ ] **Undocumented `MECH_FACTORY_ADDRESS` data structure in `deploy_mech.py`** — no docstring or comments explaining the structure or where addresses come from.
- [ ] **`deploy_mech.py` `Chain.from_string()` has no validation** — invalid chain value bubbles up without a meaningful error message.

---

## Completed

_Nothing yet._
