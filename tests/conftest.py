# -*- coding: utf-8 -*-
# ------------------------------------------------------------------------------
#
#   Copyright 2026 Valory AG
#
#   Licensed under the Apache License, Version 2.0 (the "License");
#   you may not use this file except in compliance with the License.
#   You may obtain a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
#   Unless required by applicable law or agreed to in writing, software
#   distributed under the License is distributed on an "AS IS" BASIS,
#   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#   See the License for the specific language governing permissions and
#   limitations under the License.
#
# ------------------------------------------------------------------------------

"""Shared test fixtures for the mtd unit-test suite."""

import os
from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def _redirect_home_to_tmp(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Redirect every home-style env var to ``tmp_path`` for each test.

    `Path("~/...").expanduser()` consults `HOME` on POSIX and
    `USERPROFILE` (with `HOMEDRIVE` + `HOMEPATH` as fallbacks) on Windows.
    Tests that monkeypatch `HOME` only would still resolve `~` to the
    runner's real profile on Windows; mirror to every variant so the
    workspace lands inside `tmp_path` on every platform.
    """
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    drive, _, rest = str(tmp_path).partition(os.sep)
    if drive.endswith(":"):
        monkeypatch.setenv("HOMEDRIVE", drive)
        monkeypatch.setenv("HOMEPATH", os.sep + rest)
