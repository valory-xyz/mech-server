# Code Review — Outstanding Items

All critical, high, minor, and CI/linting issues from the previous review cycle have been resolved
(166→170 tests, 100% line coverage, pylint 10.00/10). The items below are what remains.

---

## CLI improvements

The following issues currently surface as user-visible errors with no guidance. Each could be
caught early and turned into a clear, actionable message — eliminating the need for a
troubleshooting guide.

- [ ] **Validate `keys.json` against `ALL_PARTICIPANTS` at startup** — if the agent key address
  in `keys.json` is not present in `ALL_PARTICIPANTS` in `.env`, the agent fails deep inside
  the middleware with an opaque address-mismatch error. Add a startup check that compares the
  two and raises a `ClickException` with the specific mismatch and a fix hint.

- [ ] **Detect stale package hashes before `mech push-metadata`** — if `packages.json`
  fingerprints are out of sync with the on-disk tool files, metadata is published with stale
  hashes silently. Check whether `autonomy packages lock` needs to be run first (by comparing
  file hashes to `packages.json`) and warn or abort with instructions.

- [ ] **Validate `.env` values for formatting on read** — dict/list values with embedded
  whitespace or non-standard quote characters (`\u201c`/`\u201d`) cause downstream failures
  with no indication of the root cause. Parse each relevant env variable at startup and reject
  with the specific variable name and a concrete example of the correct format.

- [ ] **Detect multiline RPC values in `.env`** — editors sometimes reformat long RPC URLs
  across multiple lines, causing `Number of agent instances cannot be greater than available
  keys`. Detect newlines inside env values and fail with a targeted message.

- [ ] **Surface missing tool dependencies clearly** — when a tool file imports a package not
  listed in `component.yaml`, the current `RuntimeError` from `_import_module_from_path` is
  generic. Catch `ModuleNotFoundError` specifically and suggest adding the module to
  `dependencies` in `component.yaml`.

- [ ] **Hint on RPC filter / `AlreadyKnown` errors** — `ValueError: Filter with id: ... does
  not exist` and `AlreadyKnown` are provider-side failures that cannot be prevented, but they
  can be caught and re-raised with a message suggesting an RPC provider switch.

- [ ] **Detect port conflict before `--dev` mode starts** — check whether port `26658`
  (Tendermint) is already bound before launching and print the `lsof`/`kill` hint immediately
  rather than letting the process crash.

---

## Medium

- [ ] **Hardcoded gas values in `update_onchain.py`** — `update_metadata_onchain()` passes
  `gas=100000` and `gasPrice=web3_client.to_wei("3", "gwei")` inline at lines 165–166 and 178.
  These are appropriate defaults for Gnosis but may be too low or mis-priced on other chains
  (Polygon, Optimism). Extract to named module-level constants (`DEFAULT_GAS`,
  `DEFAULT_GAS_PRICE_GWEI`) as a minimum; consider making them overridable via env vars.

- [ ] **`_setup_env()` loop silently uses only the last matching config file** —
  `setup_flow.py:282–285`: the `for file_path in matching_paths` loop overwrites `data` on each
  iteration, so if the glob matches more than one file only the last one's data is used with no
  warning. In practice there is exactly one file today, but this is a latent bug. Either `break`
  after the first match or raise if more than one is found.

---

## Minor

- [ ] **Comment lines containing `=` are silently dropped from the generated `.env`** —
  `setup_flow.py:251`: `if "=" in line` matches comment lines such as `# KEY=example`. These
  enter the key-lookup branch, get an empty value, and are discarded via `continue` rather than
  being passed through unchanged. No current template triggers this, but it is a latent
  correctness bug. Fix: add `if line.lstrip().startswith("#"):` before the `=` check and fall
  through to `filled_lines.append(line)`.

- [ ] **`Template.substitute()` raises `KeyError` on undefined variables** —
  `add_tool_cmd.py:65`: if a template file references a `$variable` not present in
  `template_params`, Python raises a bare `KeyError`. Wrap in `try/except KeyError` and re-raise
  as a `RuntimeError` with a message indicating which variable is missing and which template is
  at fault.

- [ ] **`except Exception` too broad in `deploy_mech.py` chain validation** —
  `deploy_mech.py:93`: `Chain.from_string()` is caught with `except Exception`. Narrow to the
  actual exception type(s) the library raises (e.g. `ValueError`) so genuinely unexpected errors
  still propagate.

- [ ] **Warning in `deploy_mech.py` lacks visual emphasis** — `deploy_mech.py:112`: the
  unsupported-marketplace fallback message uses plain `click.echo()`. Use
  `click.secho(..., fg="yellow")` so the warning stands out in terminal output.

- [ ] **No validation of `author`/`tool_name` as Python identifiers in `add_tool_cmd.py`** —
  `add_tool_cmd.py:126–133`: both arguments are used as directory names and Python module names
  but are never validated. Passing a value with spaces, hyphens, or leading digits creates a
  broken package. Add a Click callback or early guard using `str.isidentifier()`.
