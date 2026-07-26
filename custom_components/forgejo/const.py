"""Constants for the Forgejo integration."""

from __future__ import annotations

from datetime import timedelta
from typing import Final

DOMAIN: Final = "forgejo"

CONF_REPOSITORIES: Final = "repositories"
CONF_VERIFY_SSL: Final = "verify_ssl"

DEFAULT_SCAN_INTERVAL: Final = timedelta(minutes=5)

# Each tracked repository costs three requests per refresh (repo, latest run,
# latest commit). Tracking everything on a busy instance at a short interval is
# the fastest way to annoy an admin, so the picker is opt-in per repository.
REQUESTS_PER_REPOSITORY: Final = 3

MANUFACTURER: Final = "Forgejo"
