"""Polling coordinator for the Forgejo integration."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable
from dataclasses import dataclass, field
import logging

from forgejo import (
    Commit,
    ForgejoAuthenticationError,
    ForgejoClient,
    ForgejoError,
    ForgejoNotFoundError,
    Release,
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
    latest_release: Release | None = None


@dataclass
class ForgejoData:
    """One snapshot of the instance."""

    server: ServerInfo
    unread_notifications: int
    assigned_issues: int | None = None
    review_requests: int | None = None
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

    async def _optional_count(
        self, request: Awaitable[int], attribute: str
    ) -> int | None:
        """Await an instance-wide count, keeping the old value if it fails.

        These searches are the slowest calls on a large instance. Losing one
        count should not make the rest of the instance unavailable.
        """
        try:
            return await request
        except ForgejoAuthenticationError:
            raise
        except ForgejoError as err:
            _LOGGER.warning("Could not refresh %s: %s", attribute, err)
            return getattr(self.data, attribute, None)

    async def _latest_run(self, owner: str, name: str) -> WorkflowRun | None:
        """Return the latest run, or ``None`` if Actions is disabled."""
        try:
            return await self.client.get_latest_workflow_run(owner, name)
        except ForgejoNotFoundError:
            # Repositories with Actions disabled answer 404 here. That is the
            # same as having no runs, not a reason to drop the repository.
            return None

    async def _async_update_data(self) -> ForgejoData:
        """Refresh everything."""
        try:
            server, unread, assigned, reviews = await asyncio.gather(
                self.client.get_version(),
                self.client.get_new_notification_count(),
                self._optional_count(
                    self.client.get_assigned_issue_count(), "assigned_issues"
                ),
                self._optional_count(
                    self.client.get_review_request_count(), "review_requests"
                ),
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
                    self._latest_run(owner, name),
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

            # Only worth a round trip when the repository payload says there is
            # something to fetch; most repositories never cut a release.
            release: Release | None = None
            if repo.releases:
                try:
                    release = await self.client.get_latest_release(owner, name)
                except ForgejoError as err:
                    _LOGGER.debug("No release info for %s: %s", slug, err)

            repositories[slug] = RepositoryData(
                repository=repo,
                latest_run=run,
                latest_commit=commit,
                latest_release=release,
            )

        return ForgejoData(
            server=server,
            unread_notifications=unread,
            assigned_issues=assigned,
            review_requests=reviews,
            repositories=repositories,
        )
