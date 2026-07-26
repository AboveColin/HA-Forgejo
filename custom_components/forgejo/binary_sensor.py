"""Binary sensors for the Forgejo integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from forgejo import TERMINAL_RUN_STATUSES

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import ForgejoConfigEntry, ForgejoCoordinator, RepositoryData
from .entity import ForgejoRepositoryEntity


@dataclass(frozen=True, kw_only=True)
class ForgejoBinarySensorDescription(BinarySensorEntityDescription):
    """Describes a repository binary sensor."""

    value_fn: Callable[[RepositoryData], bool | None]


def _ci_failing(data: RepositoryData) -> bool | None:
    """Return whether the most recent finished run failed.

    A run that is still going tells us nothing yet, and a repository with no
    runs at all has nothing to report. Both are ``None`` (unknown) rather than
    a cheerful ``False`` that would read as "CI is fine".
    """
    run = data.latest_run
    if run is None or run.status is None:
        return None
    if run.status not in TERMINAL_RUN_STATUSES:
        return None
    return run.status == "failure"


def _ci_running(data: RepositoryData) -> bool | None:
    """Return whether the most recent run is still going."""
    run = data.latest_run
    if run is None or run.status is None:
        return None
    return run.status not in TERMINAL_RUN_STATUSES


BINARY_SENSORS: tuple[ForgejoBinarySensorDescription, ...] = (
    ForgejoBinarySensorDescription(
        key="ci_failing",
        translation_key="ci_failing",
        device_class=BinarySensorDeviceClass.PROBLEM,
        value_fn=_ci_failing,
    ),
    ForgejoBinarySensorDescription(
        key="ci_running",
        translation_key="ci_running",
        device_class=BinarySensorDeviceClass.RUNNING,
        entity_registry_enabled_default=False,
        value_fn=_ci_running,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ForgejoConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up binary sensors from a config entry."""
    coordinator = entry.runtime_data
    async_add_entities(
        ForgejoRepositoryBinarySensor(coordinator, slug, description)
        for slug in coordinator.tracked_repositories
        for description in BINARY_SENSORS
    )


class ForgejoRepositoryBinarySensor(ForgejoRepositoryEntity, BinarySensorEntity):
    """A binary sensor describing one repository."""

    entity_description: ForgejoBinarySensorDescription

    def __init__(
        self,
        coordinator: ForgejoCoordinator,
        slug: str,
        description: ForgejoBinarySensorDescription,
    ) -> None:
        """Set up the binary sensor."""
        super().__init__(coordinator, slug, description.key)
        self.entity_description = description

    @property
    def is_on(self) -> bool | None:
        """Return the current state, or ``None`` when it is not knowable."""
        if (data := self.repository_data) is None:
            return None
        return self.entity_description.value_fn(data)
