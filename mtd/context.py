# -*- coding: utf-8 -*-
# ------------------------------------------------------------------------------
#
#   Copyright 2025-2026 Valory AG
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

"""Workspace context and path resolution for mech runtime."""

import os
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator, Tuple


INITIALIZED_MARKER = ".mech_initialized"
SUPPORTED_CHAINS: Tuple[str, ...] = ("gnosis", "base", "polygon", "optimism")


@dataclass(frozen=True)
class MtdContext:
    """Resolved runtime paths for a mech workspace."""

    workspace_path: Path
    env_path: Path
    config_dir: Path
    operate_dir: Path
    keys_dir: Path
    metadata_path: Path
    packages_dir: Path

    @property
    def initialized_marker_path(self) -> Path:
        """Return the workspace initialization marker path."""
        return self.workspace_path / INITIALIZED_MARKER

    def ensure_workspace_exists(self) -> None:
        """Ensure workspace root exists."""
        self.workspace_path.mkdir(parents=True, exist_ok=True)

    def is_initialized(self) -> bool:
        """Check whether the workspace has been initialized."""
        return (
            self.initialized_marker_path.exists()
            and self.config_dir.exists()
            and self.env_path.exists()
        )


def get_default_workspace() -> Path:
    """Get the default workspace path."""
    return Path("~/.operate-mech").expanduser().resolve()


@contextmanager
def workspace_cwd(context: "MtdContext") -> Iterator[None]:
    """Change to workspace root and set OPERATE_HOME, restoring both on exit."""
    previous = Path.cwd()
    previous_operate_home = os.environ.get("OPERATE_HOME")
    context.operate_dir.mkdir(parents=True, exist_ok=True)
    os.environ["OPERATE_HOME"] = str(context.operate_dir)
    os.chdir(context.workspace_path)
    try:
        yield
    finally:
        os.chdir(previous)
        if previous_operate_home is None:
            os.environ.pop("OPERATE_HOME", None)
        else:
            os.environ["OPERATE_HOME"] = previous_operate_home


def build_context() -> MtdContext:
    """Build runtime context."""
    workspace_path = get_default_workspace()
    return MtdContext(
        workspace_path=workspace_path,
        env_path=workspace_path / ".env",
        config_dir=workspace_path / "config",
        operate_dir=workspace_path,
        keys_dir=workspace_path / "keys",
        metadata_path=workspace_path / "metadata.json",
        packages_dir=workspace_path / "packages",
    )
