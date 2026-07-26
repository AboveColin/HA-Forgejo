"""Tests for Forgejo diagnostics.

These matter more than the usual smoke test: a diagnostics file gets pasted
into public bug reports, so anything identifying that leaks here leaks there.
"""

from __future__ import annotations

import json

from homeassistant.core import HomeAssistant

from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.components.diagnostics import (
    get_diagnostics_for_config_entry,
)
from pytest_homeassistant_custom_component.typing import ClientSessionGenerator

from .conftest import SLUG, TOKEN, URL


async def test_diagnostics_redacts_identifying_data(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    setup_integration: MockConfigEntry,
) -> None:
    """No address, token, repository name, branch or commit text gets out."""
    result = await get_diagnostics_for_config_entry(
        hass, hass_client, setup_integration
    )
    blob = json.dumps(result)

    for secret in (
        TOKEN,
        URL,
        "git.example.com",
        SLUG,
        "example-repo",
        "example-user",
        "Example change",
        "0123456789abcdef",
        "main",
    ):
        assert secret not in blob, f"{secret!r} leaked into diagnostics"


async def test_diagnostics_still_useful(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    setup_integration: MockConfigEntry,
) -> None:
    """What survives redaction is enough to debug with."""
    result = await get_diagnostics_for_config_entry(
        hass, hass_client, setup_integration
    )
    blob = json.dumps(result)

    assert "10.0.0" in blob  # instance version
    assert '"tracked_repository_count": 1' in blob
    assert "repository_0" in blob
