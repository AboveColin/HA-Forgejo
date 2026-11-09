"""Tests for setting up and tearing down the Forgejo integration."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

from forgejo import (
    ForgejoAuthenticationError,
    ForgejoConnectionError,
    ForgejoNotFoundError,
)

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_UNKNOWN
from homeassistant.core import HomeAssistant

from custom_components.forgejo.const import CONF_REPOSITORIES, REQUEST_TIMEOUT

from pytest_homeassistant_custom_component.common import MockConfigEntry


async def test_setup_and_unload(
    hass: HomeAssistant, setup_integration: MockConfigEntry
) -> None:
    """The entry loads and unloads cleanly."""
    assert setup_integration.state is ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(setup_integration.entry_id)
    await hass.async_block_till_done()
    assert setup_integration.state is ConfigEntryState.NOT_LOADED


async def test_setup_connection_error(
    hass: HomeAssistant, mock_client: AsyncMock, config_entry: MockConfigEntry
) -> None:
    """An unreachable instance is retried, not failed permanently."""
    mock_client.get_version.side_effect = ForgejoConnectionError("no")
    config_entry.add_to_hass(hass)

    assert not await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_setup_auth_error_starts_reauth(
    hass: HomeAssistant, mock_client: AsyncMock, config_entry: MockConfigEntry
) -> None:
    """A rejected token asks the user for a new one."""
    mock_client.get_version.side_effect = ForgejoAuthenticationError("no")
    config_entry.add_to_hass(hass)

    assert not await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.SETUP_ERROR
    flows = hass.config_entries.flow.async_progress()
    assert [flow["context"]["source"] for flow in flows] == ["reauth"]


async def test_options_update_reloads(
    hass: HomeAssistant, setup_integration: MockConfigEntry
) -> None:
    """Changing the tracked repositories reloads the entry."""
    hass.config_entries.async_update_entry(
        setup_integration, options={CONF_REPOSITORIES: []}
    )
    await hass.async_block_till_done()

    assert setup_integration.state is ConfigEntryState.LOADED
    assert not hass.states.async_entity_ids("sensor.example_user_example_repo_open_issues")


async def test_one_bad_repository_does_not_break_the_rest(
    hass: HomeAssistant, mock_client: AsyncMock, config_entry: MockConfigEntry
) -> None:
    """A repository that fails to fetch is skipped, not fatal."""
    mock_client.get_repository.side_effect = ForgejoConnectionError("gone")
    config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    # The instance sensors still exist.
    assert hass.states.get("sensor.git_example_com_unread_notifications")


async def test_client_gets_request_timeout(
    hass: HomeAssistant, mock_client: AsyncMock, config_entry: MockConfigEntry
) -> None:
    """The client is built with the longer timeout, not the library default."""
    config_entry.add_to_hass(hass)
    with patch(
        "custom_components.forgejo.ForgejoClient", return_value=mock_client
    ) as client_cls:
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    assert client_cls.call_args.kwargs["timeout"] == REQUEST_TIMEOUT


async def test_repository_without_actions_keeps_other_entities(
    hass: HomeAssistant, mock_client: AsyncMock, config_entry: MockConfigEntry
) -> None:
    """A 404 on the runs endpoint means no runs, not a missing repository."""
    mock_client.get_latest_workflow_run.side_effect = ForgejoNotFoundError("off")
    config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get("sensor.example_user_example_repo_stars").state == "7"
    run = hass.states.get("sensor.example_user_example_repo_latest_run_status")
    assert run.state == STATE_UNKNOWN


async def test_failing_counter_does_not_fail_refresh(
    hass: HomeAssistant, mock_client: AsyncMock, config_entry: MockConfigEntry
) -> None:
    """A timed out issue search leaves the other entities working."""
    mock_client.get_assigned_issue_count.side_effect = ForgejoConnectionError("slow")
    config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED
    assert hass.states.get("sensor.git_example_com_assigned_issues").state == STATE_UNKNOWN
    assert hass.states.get("sensor.git_example_com_review_requests").state == "6"
