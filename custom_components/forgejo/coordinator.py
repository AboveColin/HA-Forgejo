"""Polling coordinator for the Forgejo integration."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
import logging

from forgejo import (
    Commit,
    ForgejoAuthenticationError,
    ForgejoClient,
    ForgejoError,
    Repository,
    ServerInfo,
    WorkflowRun,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import CONF_REPOSITORIES, DEFAULT_SCAN_INTERVAL, DOMAIN

_LOGGER = logging.getLogger(__name__)

type ForgejoConfigEntry = ConfigEntry[ForgejoCoordinator]


@dataclass
class RepositoryData:
    """Everything known about one tracked repository."""

    repository: Repository
    latest_run: WorkflowRun | None = None
    latest_commit: Commit | None = None


@dataclass
class ForgejoData:
    """One snapshot of the instance."""

    server: ServerInfo
    unread_notifications: int
    repositories: dict[str, RepositoryData] = field(default_factory=dict)


class ForgejoCoordinator(DataUpdateCoordinator[ForgejoData]):
    """Fetch instance and repository state on a schedule."""

    config_entry: ForgejoConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ForgejoConfigEntry,
        client: ForgejoClient,
    ) -> None:
        """Set up the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=DEFAULT_SCAN_INTERVAL,
        )
        self.client = client

    @property
    def tracked_repositories(self) -> list[str]:
        """Return the ``owner/name`` slugs the user chose to track."""
        return list(self.config_entry.options.get(CONF_REPOSITORIES, []))

    async def _async_update_data(self) -> ForgejoData:
        """Refresh everything."""
        try:
            server, unread = await asyncio.gather(
                self.client.get_version(),
                self.client.get_new_notification_count(),
            )
        except ForgejoAuthenticationError as err:
            # Re-auth rather than a generic failure: the token was revoked or
            # its scopes changed, and only the user can fix that.
            raise ConfigEntryAuthFailed(str(err)) from err
        except ForgejoError as err:
            raise UpdateFailed(str(err)) from err

        repositories: dict[str, RepositoryData] = {}
        for slug in self.tracked_repositories:
            owner, _, name = slug.partition("/")
            if not owner or not name:
                _LOGGER.warning("Ignoring malformed repository entry %s", slug)
                continue
            try:
                repo, run, commit = await asyncio.gather(
                    self.client.get_repository(owner, name),
                    self.client.get_latest_workflow_run(owner, name),
                    self.client.get_latest_commit(owner, name),
                )
            except ForgejoAuthenticationError as err:
                raise ConfigEntryAuthFailed(str(err)) from err
            except ForgejoError as err:
                # One repository being renamed, deleted or made private must
                # not take the other repositories' entities down with it. Its
                # own entities go unavailable because its key is missing.
                _LOGGER.warning("Skipping %s this cycle: %s", slug, err)
                continue
            repositories[slug] = RepositoryData(
                repository=repo, latest_run=run, latest_commit=commit
            )

        return ForgejoData(
            server=server,
            unread_notifications=unread,
            repositories=repositories,
        )
