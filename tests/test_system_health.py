"""Tests for the Forgejo system health panel."""

from __future__ import annotations

from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from pytest_homeassistant_custom_component.common import MockConfigEntry

from .conftest import URL


async def _get_info(hass: HomeAssistant) -> dict:
    """Run the registered system health callbacks."""
    from homeassistant.components.system_health import DOMAIN as SH_DOMAIN

    return await hass.data[SH_DOMAIN]["forgejo"].info_callback(hass)


async def test_system_health_without_entries(hass: HomeAssistant) -> None:
    """Nothing configured reports zero instances."""
    assert await async_setup_component(hass, "system_health", {})
    assert await async_setup_component(hass, "forgejo", {})
    await hass.async_block_till_done()

    assert await _get_info(hass) == {"configured_instances": 0}


async def test_system_health_with_entry(
    hass: HomeAssistant,
    aioclient_mock,
    setup_integration: MockConfigEntry,
) -> None:
    """A configured instance reports reachability and version."""
    assert await async_setup_component(hass, "system_health", {})
    await hass.async_block_till_done()
    aioclient_mock.get(URL, text="")

    info = await _get_info(hass)

    assert info["configured_instances"] == 1
    assert info["instance_0_version"] == "10.0.0"
    assert await info["instance_0_reachable"] == "ok"
