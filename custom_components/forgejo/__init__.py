"""The Forgejo integration."""

from __future__ import annotations

from forgejo import ForgejoClient

from homeassistant.const import CONF_TOKEN, CONF_URL, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import CONF_VERIFY_SSL
from .coordinator import ForgejoConfigEntry, ForgejoCoordinator
from .entity import instance_device_info

PLATFORMS: list[Platform] = [Platform.BINARY_SENSOR, Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ForgejoConfigEntry) -> bool:
    """Set up Forgejo from a config entry."""
    verify_ssl = entry.data.get(CONF_VERIFY_SSL, True)
    client = ForgejoClient(
        entry.data[CONF_URL],
        token=entry.data[CONF_TOKEN],
        session=async_get_clientsession(hass, verify_ssl=verify_ssl),
        verify_ssl=verify_ssl,
    )

    coordinator = ForgejoCoordinator(hass, entry, client)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    # Register the instance device before the platforms run. The repository
    # devices point at it with via_device, and whichever platform loads first
    # would otherwise reference a device that does not exist yet.
    dr.async_get(hass).async_get_or_create(
        config_entry_id=entry.entry_id, **instance_device_info(coordinator)
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_reload_entry))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ForgejoConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def _async_reload_entry(hass: HomeAssistant, entry: ForgejoConfigEntry) -> None:
    """Reload after the tracked-repository list changed.

    Adding or removing a repository changes which entities exist, and entities
    are only created during platform setup.
    """
    await hass.config_entries.async_reload(entry.entry_id)
