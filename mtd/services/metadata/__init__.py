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

"""Metadata services."""

from mtd.services.metadata.generate import generate_metadata
from mtd.services.metadata.publish import DEFAULT_IPFS_NODE, publish_metadata_to_ipfs
from mtd.services.metadata.update_onchain import update_metadata_onchain

__all__ = [
    "DEFAULT_IPFS_NODE",
    "generate_metadata",
    "publish_metadata_to_ipfs",
    "update_metadata_onchain",
]
