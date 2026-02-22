# Code Review — Outstanding Items

All critical, high, minor, and CI/linting issues from the previous review cycle have been resolved
(166→170 tests, 100% line coverage, pylint 10.00/10). The items below are what remains.

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
