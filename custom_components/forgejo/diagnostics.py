"""Diagnostics for the Forgejo integration.

Users paste this output into issue reports, so anything that could identify or
authenticate them is redacted here rather than trusted to be uninteresting.
"""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_TOKEN, CONF_URL
from homeassistant.core import HomeAssistant

from .coordinator import ForgejoConfigEntry

# async_redact_data matches keys exactly, so every variant has to be listed.
TO_REDACT = {
    CONF_TOKEN,
    CONF_URL,
    "access_token",
    "api_token",
    "author",
    "display_title",
    "full_name",
    "head_branch",
    "head_sha",
    "html_url",
    "message",
    "password",
    "repositories",
    "sha",
    "token",
    "url",
    "username",
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ForgejoConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator = entry.runtime_data
    data = coordinator.data

    repositories: dict[str, Any] = {}
    if data is not None:
        for index, (slug, repo_data) in enumerate(data.repositories.items()):
            # Repository names carry project and employer information. The
            # counters are what actually matters for debugging.
            repositories[f"repository_{index}"] = {
                "private": repo_data.repository.private,
                "archived": repo_data.repository.archived,
                "fork": repo_data.repository.fork,
                "has_actions": repo_data.repository.has_actions,
                "open_issues": repo_data.repository.open_issues,
                "open_pull_requests": repo_data.repository.open_pull_requests,
                "stars": repo_data.repository.stars,
                "releases": repo_data.repository.releases,
                "latest_run": async_redact_data(
                    asdict(repo_data.latest_run), TO_REDACT
                )
                if repo_data.latest_run
                else None,
                "has_commit": repo_data.latest_commit is not None,
            }
            del slug  # deliberately not reported

    return {
        "entry": {
            # Only the count. The option itself is a list of "owner/name"
            # slugs, which is exactly the thing a user does not want to paste
            # into a public issue.
            "tracked_repository_count": len(entry.options.get("repositories", [])),
            "data": async_redact_data(dict(entry.data), TO_REDACT),
        },
        "server_version": data.server.version if data else None,
        "unread_notifications": data.unread_notifications if data else None,
        "last_update_success": coordinator.last_update_success,
        "repositories": repositories,
    }
