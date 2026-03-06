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

"""CLI command modules."""

from mtd.commands.add_tool_cmd import add_tool
from mtd.commands.context_utils import get_mtd_context
from mtd.commands.prepare_metadata_cmd import prepare_metadata
from mtd.commands.run_cmd import run
from mtd.commands.setup_cmd import setup
from mtd.commands.stop_cmd import stop
from mtd.commands.update_metadata_cmd import update_metadata

__all__ = [
    "add_tool",
    "get_mtd_context",
    "prepare_metadata",
    "run",
    "setup",
    "stop",
    "update_metadata",
]
