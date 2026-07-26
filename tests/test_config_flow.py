"""Tests for the Forgejo config and options flow."""

from __future__ import annotations

from unittest.mock import AsyncMock

from forgejo import (
    ForgejoAuthenticationError,
    ForgejoConnectionError,
    ForgejoResponseError,
)
import pytest

from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_TOKEN, CONF_URL
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from custom_components.forgejo.config_flow import _normalise_url
from custom_components.forgejo.const import (
    CONF_REPOSITORIES,
    CONF_VERIFY_SSL,
    DOMAIN,
)

from pytest_homeassistant_custom_component.common import MockConfigEntry

from .conftest import SLUG, TOKEN, URL


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("https://git.example.com", "https://git.example.com"),
        ("git.example.com", "https://git.example.com"),
        ("  https://git.example.com/  ", "https://git.example.com"),
        ("https://git.example.com/api/v1", "https://git.example.com"),
        ("https://git.example.com/api/v1/", "https://git.example.com"),
        ("https://git.example.com/api", "https://git.example.com"),
        ("https://git.example.com/api/swagger", "https://git.example.com"),
        ("http://git.example.com:3000", "http://git.example.com:3000"),
        ("https://example.com/forge", "https://example.com/forge"),
    ],
)
def test_normalise_url(raw: str, expected: str) -> None:
    """The address field forgives the usual things people paste."""
    assert _normalise_url(raw) == expected


async def test_user_flow(hass: HomeAssistant, mock_client: AsyncMock) -> None:
    """A valid address and token creates an entry."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_URL: f"{URL}/api/v1", CONF_TOKEN: TOKEN, CONF_VERIFY_SSL: True},
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "git.example.com (example-user)"
    assert result["data"] == {
        CONF_URL: URL,
        CONF_TOKEN: TOKEN,
        CONF_VERIFY_SSL: True,
    }
    assert result["options"] == {CONF_REPOSITORIES: []}


@pytest.mark.parametrize(
    ("error", "expected"),
    [
        (ForgejoAuthenticationError("no"), "invalid_auth"),
        (ForgejoConnectionError("no"), "cannot_connect"),
        (ForgejoResponseError("no"), "invalid_response"),
        (RuntimeError("no"), "unknown"),
    ],
)
async def test_user_flow_errors(
    hass: HomeAssistant,
    mock_client: AsyncMock,
    error: Exception,
    expected: str,
) -> None:
    """Every failure shows a message and lets the user try again."""
    mock_client.get_version.side_effect = error

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_URL: URL, CONF_TOKEN: TOKEN}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": expected}

    # Recovering within the same flow works.
    mock_client.get_version.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_URL: URL, CONF_TOKEN: TOKEN}
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_user_flow_duplicate(
    hass: HomeAssistant, mock_client: AsyncMock, config_entry: MockConfigEntry
) -> None:
    """The same instance and account cannot be added twice."""
    config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_URL: URL, CONF_TOKEN: TOKEN}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_reauth_flow(
    hass: HomeAssistant, mock_client: AsyncMock, setup_integration: MockConfigEntry
) -> None:
    """A fresh token replaces the rejected one."""
    result = await setup_integration.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_TOKEN: "new-token"}
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert setup_integration.data[CONF_TOKEN] == "new-token"


async def test_reauth_flow_still_invalid(
    hass: HomeAssistant, mock_client: AsyncMock, setup_integration: MockConfigEntry
) -> None:
    """A token that is also wrong keeps the form open."""
    mock_client.get_version.side_effect = ForgejoAuthenticationError("no")

    result = await setup_integration.start_reauth_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_TOKEN: "also-wrong"}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}
    assert setup_integration.data[CONF_TOKEN] == TOKEN


async def test_options_flow(
    hass: HomeAssistant, mock_client: AsyncMock, setup_integration: MockConfigEntry
) -> None:
    """Repositories can be chosen from the listing."""
    result = await hass.config_entries.options.async_init(
        setup_integration.entry_id
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {CONF_REPOSITORIES: [SLUG]}
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert setup_integration.options == {CONF_REPOSITORIES: [SLUG]}


async def test_options_flow_keeps_missing_repository(
    hass: HomeAssistant,
    mock_client: AsyncMock,
    setup_integration: MockConfigEntry,
) -> None:
    """A tracked repository absent from the listing stays selectable."""
    mock_client.list_repositories.return_value = []

    result = await hass.config_entries.options.async_init(
        setup_integration.entry_id
    )
    options = result["data_schema"].schema[CONF_REPOSITORIES].config["options"]
    assert SLUG in options


async def test_options_flow_cannot_connect(
    hass: HomeAssistant,
    mock_client: AsyncMock,
    setup_integration: MockConfigEntry,
) -> None:
    """The picker aborts rather than showing an empty list."""
    mock_client.list_repositories.side_effect = ForgejoConnectionError("no")

    result = await hass.config_entries.options.async_init(
        setup_integration.entry_id
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "cannot_connect"
