"""System health for the Forgejo integration."""

from __future__ import annotations

from typing import Any

from homeassistant.components import system_health
from homeassistant.const import CONF_URL
from homeassistant.core import HomeAssistant, callback

from .const import DOMAIN


@callback
def async_register(
    hass: HomeAssistant, register: system_health.SystemHealthRegistration
) -> None:
    """Register the system health callbacks."""
    register.async_register_info(system_health_info)


async def system_health_info(hass: HomeAssistant) -> dict[str, Any]:
    """Report whether each configured instance is reachable."""
    entries = hass.config_entries.async_loaded_entries(DOMAIN)
    if not entries:
        return {"configured_instances": 0}

    info: dict[str, Any] = {"configured_instances": len(entries)}
    for index, entry in enumerate(entries):
        coordinator = entry.runtime_data
        info[f"instance_{index}_reachable"] = system_health.async_check_can_reach_url(
            hass, entry.data[CONF_URL]
        )
        info[f"instance_{index}_version"] = (
            coordinator.data.server.version if coordinator.data else "unknown"
        )
    return info
