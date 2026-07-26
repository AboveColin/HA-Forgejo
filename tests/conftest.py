"""Shared fixtures for the Forgejo tests."""

from __future__ import annotations

from collections.abc import Generator
from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

from forgejo import Commit, Repository, ServerInfo, User, WorkflowRun
import pytest

from homeassistant.const import CONF_TOKEN, CONF_URL
from homeassistant.core import HomeAssistant

from custom_components.forgejo.const import (
    CONF_REPOSITORIES,
    CONF_VERIFY_SSL,
    DOMAIN,
)

from pytest_homeassistant_custom_component.common import MockConfigEntry

URL = "https://git.example.com"
TOKEN = "example-token"
SLUG = "example-user/example-repo"


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(
    enable_custom_integrations: None,
) -> None:
    """Let Home Assistant load the integration from custom_components."""


@pytest.fixture
def server_info() -> ServerInfo:
    """Return a version response."""
    return ServerInfo(version="10.0.0")


@pytest.fixture
def user() -> User:
    """Return an authenticated user."""
    return User(
        id=1, login="example-user", full_name="Example User", is_admin=False
    )


@pytest.fixture
def repository() -> Repository:
    """Return a repository."""
    return Repository(
        id=2,
        name="example-repo",
        owner="example-user",
        full_name=SLUG,
        private=False,
        archived=False,
        fork=False,
        mirror=False,
        default_branch="main",
        description="An example repository",
        language="Python",
        html_url=f"{URL}/{SLUG}",
        has_actions=True,
        open_issues=3,
        open_pull_requests=2,
        stars=7,
        forks=1,
        watchers=7,
        releases=4,
        size_kb=1024,
        updated_at=datetime(2026, 1, 1, tzinfo=UTC),
    )


@pytest.fixture
def workflow_run() -> WorkflowRun:
    """Return a finished, successful workflow run."""
    return WorkflowRun(
        id=12,
        name="CI",
        workflow_id="ci.yml",
        status="success",
        event="push",
        head_branch="main",
        head_sha="0123456789abcdef",
        run_number=12,
        display_title="Example change",
        url=f"{URL}/{SLUG}/actions/runs/12",
        started_at=datetime(2026, 1, 1, tzinfo=UTC),
        updated_at=datetime(2026, 1, 1, 0, 5, tzinfo=UTC),
    )


@pytest.fixture
def commit() -> Commit:
    """Return the tip commit."""
    return Commit(
        sha="0123456789abcdef",
        message="Example change",
        author="example-user",
        html_url=f"{URL}/{SLUG}/commit/0123456789abcdef",
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
    )


@pytest.fixture
def mock_client(
    server_info: ServerInfo,
    user: User,
    repository: Repository,
    workflow_run: WorkflowRun,
    commit: Commit,
) -> Generator[AsyncMock]:
    """Patch ForgejoClient everywhere the integration constructs one."""
    client = AsyncMock()
    client.get_version.return_value = server_info
    client.get_authenticated_user.return_value = user
    client.get_new_notification_count.return_value = 5
    client.list_repositories.return_value = [repository]
    client.get_repository.return_value = repository
    client.get_latest_workflow_run.return_value = workflow_run
    client.get_latest_commit.return_value = commit

    with (
        patch(
            "custom_components.forgejo.config_flow.ForgejoClient",
            return_value=client,
        ),
        patch(
            "custom_components.forgejo.ForgejoClient",
            return_value=client,
        ),
    ):
        yield client


@pytest.fixture
def config_entry() -> MockConfigEntry:
    """Return a configured entry tracking one repository."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="git.example.com (example-user)",
        unique_id="git.example.com:example-user",
        data={CONF_URL: URL, CONF_TOKEN: TOKEN, CONF_VERIFY_SSL: True},
        options={CONF_REPOSITORIES: [SLUG]},
    )


@pytest.fixture
async def setup_integration(
    hass: HomeAssistant, mock_client: AsyncMock, config_entry: MockConfigEntry
) -> MockConfigEntry:
    """Add and set up the config entry."""
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    return config_entry
