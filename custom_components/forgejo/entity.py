"""Shared entity bases.

Device identity is defined here once. Letting each platform build its own
``DeviceInfo`` for the same device makes the registry entry flip between
variants depending on which platform loads first.
"""

from __future__ import annotations

from yarl import URL

from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER
from .coordinator import ForgejoCoordinator, RepositoryData


def instance_device_info(coordinator: ForgejoCoordinator) -> DeviceInfo:
    """Return the device describing the instance as a whole."""
    url = coordinator.config_entry.data.get("url", "")
    return DeviceInfo(
        identifiers={(DOMAIN, coordinator.config_entry.entry_id)},
        entry_type=DeviceEntryType.SERVICE,
        manufacturer=MANUFACTURER,
        name=URL(url).host or DOMAIN,
        configuration_url=url or None,
        sw_version=coordinator.data.server.version if coordinator.data else None,
    )


class ForgejoEntity(CoordinatorEntity[ForgejoCoordinator]):
    """Base for entities describing the instance as a whole."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: ForgejoCoordinator, key: str) -> None:
        """Set up the entity."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_{key}"
        self._attr_device_info = instance_device_info(coordinator)


class ForgejoRepositoryEntity(CoordinatorEntity[ForgejoCoordinator]):
    """Base for entities describing one repository."""

    _attr_has_entity_name = True

    def __init__(
        self, coordinator: ForgejoCoordinator, slug: str, key: str
    ) -> None:
        """Set up the entity."""
        super().__init__(coordinator)
        self._slug = slug
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_{slug}_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{coordinator.config_entry.entry_id}_{slug}")},
            entry_type=DeviceEntryType.SERVICE,
            manufacturer=MANUFACTURER,
            model="Repository",
            name=slug,
            via_device=(DOMAIN, coordinator.config_entry.entry_id),
            configuration_url=self._repository_url,
        )

    @property
    def _repository_url(self) -> str | None:
        """Return the browser URL of the repository."""
        base = self.coordinator.config_entry.data.get("url", "").rstrip("/")
        return f"{base}/{self._slug}" if base else None

    @property
    def repository_data(self) -> RepositoryData | None:
        """Return this repository's slice of the last refresh, if present."""
        if self.coordinator.data is None:
            return None
        return self.coordinator.data.repositories.get(self._slug)

    @property
    def available(self) -> bool:
        """Report unavailable when this repository was missing this cycle."""
        return super().available and self.repository_data is not None
