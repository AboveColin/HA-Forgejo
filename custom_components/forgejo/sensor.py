"""Sensors for the Forgejo integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import EntityCategory, UnitOfInformation
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import ForgejoConfigEntry, ForgejoCoordinator, RepositoryData
from .entity import ForgejoEntity, ForgejoRepositoryEntity


@dataclass(frozen=True, kw_only=True)
class ForgejoSensorDescription(SensorEntityDescription):
    """Describes an instance-level sensor."""

    value_fn: Callable[[ForgejoCoordinator], int | str | None]


@dataclass(frozen=True, kw_only=True)
class ForgejoRepositorySensorDescription(SensorEntityDescription):
    """Describes a repository-level sensor."""

    value_fn: Callable[[RepositoryData], int | str | datetime | None]


INSTANCE_SENSORS: tuple[ForgejoSensorDescription, ...] = (
    ForgejoSensorDescription(
        key="unread_notifications",
        translation_key="unread_notifications",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda c: c.data.unread_notifications if c.data else None,
    ),
    ForgejoSensorDescription(
        key="version",
        translation_key="version",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda c: c.data.server.version if c.data else None,
    ),
)

REPOSITORY_SENSORS: tuple[ForgejoRepositorySensorDescription, ...] = (
    ForgejoRepositorySensorDescription(
        key="open_issues",
        translation_key="open_issues",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: d.repository.open_issues,
    ),
    ForgejoRepositorySensorDescription(
        key="open_pull_requests",
        translation_key="open_pull_requests",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: d.repository.open_pull_requests,
    ),
    ForgejoRepositorySensorDescription(
        key="stars",
        translation_key="stars",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: d.repository.stars,
    ),
    ForgejoRepositorySensorDescription(
        key="forks",
        translation_key="forks",
        entity_registry_enabled_default=False,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: d.repository.forks,
    ),
    ForgejoRepositorySensorDescription(
        key="releases",
        translation_key="releases",
        entity_registry_enabled_default=False,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: d.repository.releases,
    ),
    ForgejoRepositorySensorDescription(
        key="size",
        translation_key="size",
        device_class=SensorDeviceClass.DATA_SIZE,
        native_unit_of_measurement=UnitOfInformation.KILOBYTES,
        suggested_unit_of_measurement=UnitOfInformation.MEGABYTES,
        entity_registry_enabled_default=False,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: d.repository.size_kb,
    ),
    ForgejoRepositorySensorDescription(
        key="last_commit",
        translation_key="last_commit",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda d: d.latest_commit.created_at if d.latest_commit else None,
    ),
    ForgejoRepositorySensorDescription(
        key="latest_run_status",
        translation_key="latest_run_status",
        value_fn=lambda d: d.latest_run.status if d.latest_run else None,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ForgejoConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up sensors from a config entry."""
    coordinator = entry.runtime_data
    entities: list[SensorEntity] = [
        ForgejoInstanceSensor(coordinator, description)
        for description in INSTANCE_SENSORS
    ]
    entities.extend(
        ForgejoRepositorySensor(coordinator, slug, description)
        for slug in coordinator.tracked_repositories
        for description in REPOSITORY_SENSORS
    )
    async_add_entities(entities)


class ForgejoInstanceSensor(ForgejoEntity, SensorEntity):
    """A sensor describing the instance."""

    entity_description: ForgejoSensorDescription

    def __init__(
        self, coordinator: ForgejoCoordinator, description: ForgejoSensorDescription
    ) -> None:
        """Set up the sensor."""
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def native_value(self) -> int | str | None:
        """Return the current value."""
        return self.entity_description.value_fn(self.coordinator)


class ForgejoRepositorySensor(ForgejoRepositoryEntity, SensorEntity):
    """A sensor describing one repository."""

    entity_description: ForgejoRepositorySensorDescription

    def __init__(
        self,
        coordinator: ForgejoCoordinator,
        slug: str,
        description: ForgejoRepositorySensorDescription,
    ) -> None:
        """Set up the sensor."""
        super().__init__(coordinator, slug, description.key)
        self.entity_description = description

    @property
    def native_value(self) -> int | str | datetime | None:
        """Return the current value, or ``None`` if the repo was not fetched."""
        if (data := self.repository_data) is None:
            return None
        return self.entity_description.value_fn(data)

    @property
    def extra_state_attributes(self) -> dict[str, str | int | None] | None:
        """Expose run and commit detail on the sensors that have some."""
        if (data := self.repository_data) is None:
            return None
        if self.entity_description.key == "latest_run_status" and data.latest_run:
            run = data.latest_run
            return {
                "workflow": run.name,
                "run_number": run.run_number,
                "event": run.event,
                "branch": run.head_branch,
                "title": run.display_title,
                "url": run.url,
            }
        if self.entity_description.key == "last_commit" and data.latest_commit:
            commit = data.latest_commit
            return {
                "sha": commit.sha,
                "message": commit.message,
                "author": commit.author,
                "url": commit.html_url,
            }
        return None
