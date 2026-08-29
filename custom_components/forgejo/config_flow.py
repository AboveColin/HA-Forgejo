"""Config and options flow for the Forgejo integration."""

from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any

from forgejo import (
    ForgejoAuthenticationError,
    ForgejoClient,
    ForgejoConnectionError,
    ForgejoError,
)
import voluptuous as vol
from yarl import URL

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_TOKEN, CONF_URL
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)
from homeassistant.helpers.selector import (
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from .const import CONF_REPOSITORIES, CONF_VERIFY_SSL, DOMAIN

_LOGGER = logging.getLogger(__name__)

# A bare `str` renders the secret in clear text in the config form. TextSelector
# with type PASSWORD makes the browser treat it as a password field.
_SECRET = TextSelector(TextSelectorConfig(type=TextSelectorType.PASSWORD))

STEP_USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_URL): str,
        vol.Required(CONF_TOKEN): _SECRET,
        vol.Optional(CONF_VERIFY_SSL, default=True): bool,
    }
)


def _normalise_url(raw: str) -> str:
    """Accept what people paste: bare hosts, trailing slashes, API paths."""
    candidate = raw.strip().rstrip("/")
    if not candidate.startswith(("http://", "https://")):
        candidate = f"https://{candidate}"
    url = URL(candidate)
    # Pasting the URL of the API browser is a common way to get a confusing
    # 404 later, so strip the suffix here instead.
    path = url.path.rstrip("/")
    for suffix in ("/api/v1", "/api/swagger", "/api"):
        if path.endswith(suffix):
            path = path[: -len(suffix)]
    return str(url.with_path(path)).rstrip("/")


class ForgejoConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle setting up a Forgejo instance."""

    VERSION = 1

    def __init__(self) -> None:
        """Set up the flow."""
        self._reauth_entry: ConfigEntry | None = None

    async def _async_validate(
        self, url: str, token: str, verify_ssl: bool
    ) -> tuple[str | None, str | None]:
        """Return ``(user_login, error_key)`` for the given credentials."""
        client = ForgejoClient(
            url,
            token=token,
            session=async_get_clientsession(self.hass, verify_ssl=verify_ssl),
            verify_ssl=verify_ssl,
        )
        try:
            await client.get_version()
            user = await client.get_authenticated_user()
        except ForgejoAuthenticationError:
            return None, "invalid_auth"
        except ForgejoConnectionError:
            return None, "cannot_connect"
        except ForgejoError:
            return None, "invalid_response"
        except Exception:  # noqa: BLE001 - the flow must never leave a traceback in the UI
            _LOGGER.exception("Unexpected error validating the Forgejo connection")
            return None, "unknown"
        return user.login, None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            url = _normalise_url(user_input[CONF_URL])
            verify_ssl = user_input.get(CONF_VERIFY_SSL, True)
            login, error = await self._async_validate(
                url, user_input[CONF_TOKEN], verify_ssl
            )
            if error is None:
                await self.async_set_unique_id(f"{URL(url).host}:{login}")
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=f"{URL(url).host} ({login})",
                    data={
                        CONF_URL: url,
                        CONF_TOKEN: user_input[CONF_TOKEN],
                        CONF_VERIFY_SSL: verify_ssl,
                    },
                    options={CONF_REPOSITORIES: []},
                )
            errors["base"] = error

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_SCHEMA, errors=errors
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Start re-authentication after the token stopped working."""
        self._reauth_entry = self.hass.config_entries.async_get_entry(
            self.context["entry_id"]
        )
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask for a fresh token."""
        errors: dict[str, str] = {}
        entry = self._reauth_entry
        assert entry is not None

        if user_input is not None:
            _, error = await self._async_validate(
                entry.data[CONF_URL],
                user_input[CONF_TOKEN],
                entry.data.get(CONF_VERIFY_SSL, True),
            )
            if error is None:
                return self.async_update_reload_and_abort(
                    entry, data_updates={CONF_TOKEN: user_input[CONF_TOKEN]}
                )
            errors["base"] = error

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema({vol.Required(CONF_TOKEN): _SECRET}),
            description_placeholders={"url": entry.data[CONF_URL]},
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> ForgejoOptionsFlow:
        """Return the options flow."""
        return ForgejoOptionsFlow()


class ForgejoOptionsFlow(OptionsFlow):
    """Let the user choose which repositories to track."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Show the repository picker."""
        if user_input is not None:
            return self.async_create_entry(data=user_input)

        entry = self.config_entry
        verify_ssl = entry.data.get(CONF_VERIFY_SSL, True)
        client = ForgejoClient(
            entry.data[CONF_URL],
            token=entry.data[CONF_TOKEN],
            session=async_get_clientsession(self.hass, verify_ssl=verify_ssl),
            verify_ssl=verify_ssl,
        )
        try:
            repositories = await client.list_repositories()
        except ForgejoError:
            return self.async_abort(reason="cannot_connect")

        selected = entry.options.get(CONF_REPOSITORIES, [])
        # Keep any already-tracked repository in the list even if it dropped
        # out of the listing, so saving the form does not silently untrack it.
        choices = sorted({repo.full_name for repo in repositories} | set(selected))

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_REPOSITORIES, default=selected
                    ): SelectSelector(
                        SelectSelectorConfig(
                            options=choices,
                            multiple=True,
                            mode=SelectSelectorMode.DROPDOWN,
                            custom_value=True,
                            sort=True,
                        )
                    )
                }
            ),
        )
