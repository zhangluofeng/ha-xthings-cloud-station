"""Runtime data for Xthings Cloud remote access and SSO."""

from ha_xthings_cloud import (
    XthingsCloudApiClient,
    XthingsCloudAuthError,
    XthingsCloudWebSocket,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import CONF_REFRESH_TOKEN, LOGGER
from .sso import XthingsSsoManager

type XthingsCloudConfigEntry = ConfigEntry[XthingsCloudRuntimeData]


class XthingsCloudRuntimeData:
    """Runtime data used by the remote access and SSO features."""

    config_entry: XthingsCloudConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        client: XthingsCloudApiClient,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the coordinator."""
        self.hass = hass
        self.config_entry = entry
        self.client = client
        self.sso_manager = XthingsSsoManager(hass, entry, client)
        self.websocket: XthingsCloudWebSocket | None = None

    async def _async_ensure_token_valid(self) -> None:
        """Ensure the token is valid, refresh if expired.

        Raises ConfigEntryAuthFailed if refresh fails.
        """
        if not self.client.is_token_expired():
            return
        try:
            token_data = await self.client.async_refresh_token(
                self.config_entry.data[CONF_REFRESH_TOKEN]
            )
        except XthingsCloudAuthError as err:
            raise ConfigEntryAuthFailed(
                "Token expired and refresh failed, re-authentication required"
            ) from err
        self.hass.config_entries.async_update_entry(
            self.config_entry,
            data={
                **self.config_entry.data,
                CONF_TOKEN: token_data["token"],
                CONF_REFRESH_TOKEN: token_data["refresh_token"],
            },
        )
        self.client.token = token_data["token"]

    async def async_ensure_token_valid(self) -> None:
        """Refresh the API token when it has expired."""
        await self._async_ensure_token_valid()

    async def async_start_websocket(self) -> None:
        """Start the cloud WebSocket connection."""
        if self.websocket:
            return
        self.websocket = XthingsCloudWebSocket(
            session=async_get_clientsession(self.hass),
            token=self.config_entry.data[CONF_TOKEN],
            on_device_status=self._handle_ws_device_status,
            on_token_expired=self._handle_ws_token_expired,
        )
        await self.websocket.async_start()

    async def async_stop_websocket(self) -> None:
        """Stop the cloud WebSocket connection."""
        if self.websocket:
            await self.websocket.async_stop()
            self.websocket = None

    def _handle_ws_device_status(
        self, device_uuid: str, status: dict[str, object]
    ) -> None:
        """Log real-time device updates without creating HA entities."""
        LOGGER.debug("WebSocket updated device status for %s: %s", device_uuid, status)

    async def _handle_ws_token_expired(self) -> None:
        """Refresh the token used by the WebSocket."""
        try:
            await self._async_ensure_token_valid()
        except ConfigEntryAuthFailed:
            LOGGER.error("WebSocket token refresh failed")
            return
        if self.websocket:
            self.websocket.token = self.client.token
