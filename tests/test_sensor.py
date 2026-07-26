"""Tests for the Forgejo entities."""

from __future__ import annotations

from dataclasses import replace
from unittest.mock import AsyncMock

from forgejo import ForgejoConnectionError

from homeassistant.const import STATE_UNKNOWN
from homeassistant.core import HomeAssistant

from pytest_homeassistant_custom_component.common import MockConfigEntry


async def test_instance_sensors(
    hass: HomeAssistant, setup_integration: MockConfigEntry
) -> None:
    """The instance device reports notifications and version."""
    assert (
        hass.states.get("sensor.git_example_com_unread_notifications").state == "5"
    )
    assert hass.states.get("sensor.git_example_com_version").state == "10.0.0"
    assert hass.states.get("sensor.git_example_com_assigned_issues").state == "4"
    assert hass.states.get("sensor.git_example_com_review_requests").state == "6"


async def test_latest_release(
    hass: HomeAssistant, setup_integration: MockConfigEntry
) -> None:
    """The newest release tag lands on the repository device."""
    state = hass.states.get("sensor.example_user_example_repo_latest_release")
    assert state.state == "v1.2.3"
    assert state.attributes["name"] == "Example release"
    assert state.attributes["prerelease"] is False


async def test_release_not_fetched_without_any(
    hass: HomeAssistant, mock_client: AsyncMock, config_entry: MockConfigEntry
) -> None:
    """A repository with no releases costs no extra request."""
    mock_client.get_repository.return_value = replace(
        mock_client.get_repository.return_value, releases=0
    )

    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    mock_client.get_latest_release.assert_not_called()
    assert (
        hass.states.get("sensor.example_user_example_repo_latest_release").state
        == STATE_UNKNOWN
    )


async def test_repository_sensors(
    hass: HomeAssistant, setup_integration: MockConfigEntry
) -> None:
    """Per-repository counters land on the repository device."""
    assert hass.states.get("sensor.example_user_example_repo_open_issues").state == "3"
    assert hass.states.get("sensor.example_user_example_repo_open_pull_requests").state == "2"
    assert hass.states.get("sensor.example_user_example_repo_stars").state == "7"

    commit = hass.states.get("sensor.example_user_example_repo_last_commit")
    assert commit.state == "2026-01-01T00:00:00+00:00"
    assert commit.attributes["author"] == "example-user"

    run = hass.states.get("sensor.example_user_example_repo_latest_run_status")
    assert run.state == "success"
    assert run.attributes["run_number"] == 12


async def test_ci_binary_sensor(
    hass: HomeAssistant, setup_integration: MockConfigEntry
) -> None:
    """A passing run means the problem sensor is off."""
    assert hass.states.get("binary_sensor.example_user_example_repo_ci_failing").state == "off"


async def test_ci_failing(
    hass: HomeAssistant, mock_client: AsyncMock, config_entry: MockConfigEntry
) -> None:
    """A failed run turns the problem sensor on."""
    mock_client.get_latest_workflow_run.return_value = _with_status(
        mock_client.get_latest_workflow_run.return_value, "failure"
    )

    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get("binary_sensor.example_user_example_repo_ci_failing").state == "on"


async def test_ci_unknown_while_running(
    hass: HomeAssistant, mock_client: AsyncMock, config_entry: MockConfigEntry
) -> None:
    """An unfinished run is unknown, never 'off' — automations must not fire early."""
    mock_client.get_latest_workflow_run.return_value = _with_status(
        mock_client.get_latest_workflow_run.return_value, "running"
    )

    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert (
        hass.states.get("binary_sensor.example_user_example_repo_ci_failing").state
        == STATE_UNKNOWN
    )


async def test_ci_unknown_without_runs(
    hass: HomeAssistant, mock_client: AsyncMock, config_entry: MockConfigEntry
) -> None:
    """A repository with no Actions runs is unknown, not 'off'."""
    mock_client.get_latest_workflow_run.return_value = None

    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert (
        hass.states.get("binary_sensor.example_user_example_repo_ci_failing").state
        == STATE_UNKNOWN
    )


async def test_release_fetch_failure_is_not_fatal(
    hass: HomeAssistant, mock_client: AsyncMock, config_entry: MockConfigEntry
) -> None:
    """A failing release lookup leaves the rest of the repository intact."""
    mock_client.get_latest_release.side_effect = ForgejoConnectionError("gone")

    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert (
        hass.states.get("sensor.example_user_example_repo_latest_release").state
        == STATE_UNKNOWN
    )
    assert hass.states.get("sensor.example_user_example_repo_open_issues").state == "3"


def _with_status(run, status: str):
    """Return a copy of a run with a different status."""
    return replace(run, status=status)
