"""Xthings Cloud integration for Home Assistant."""

from ha_xthings_cloud import XthingsCloudApiClient, XthingsCloudApiError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.instance_id import async_get as async_get_instance_id
from homeassistant.helpers.typing import ConfigType

from .const import CONF_REMOTE_ACCESS, DOMAIN, LOGGER
from .coordinator import XthingsCloudConfigEntry, XthingsCloudRuntimeData
from .remote_access import async_disable_remote_access, async_enable_remote_access
from .sso import XthingsSsoView

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Xthings Cloud integration."""
    hass.http.register_view(XthingsSsoView)
    return True


async def async_setup_entry(
    hass: HomeAssistant, entry: XthingsCloudConfigEntry
) -> None:
    """Set up config entry."""
    session = async_get_clientsession(hass)
    client = XthingsCloudApiClient(session, token=entry.data[CONF_TOKEN])
    runtime_data = XthingsCloudRuntimeData(hass, client, entry)
    entry.runtime_data = runtime_data
    await runtime_data.async_start_websocket()

    if entry.options.get(CONF_REMOTE_ACCESS, False):
        await _async_bind_and_enable_remote_access(hass, client)

    remote_access_enabled = entry.options.get(CONF_REMOTE_ACCESS, False)
    async def _async_entry_updated(hass: HomeAssistant, entry: ConfigEntry) -> None:
        nonlocal remote_access_enabled
        enabled = entry.options.get(CONF_REMOTE_ACCESS, False)
        if enabled == remote_access_enabled:
            return
        remote_access_enabled = enabled
        await _async_options_updated(hass, entry)

    entry.async_on_unload(entry.add_update_listener(_async_entry_updated))


async def async_unload_entry(
    hass: HomeAssistant, entry: XthingsCloudConfigEntry
) -> None:
    """Unload config entry."""
    await async_disable_remote_access(hass)
    session = async_get_clientsession(hass)
    client = XthingsCloudApiClient(session, token=entry.data[CONF_TOKEN])
    instance_id = await async_get_instance_id(hass)
    try:
        await client.async_unbind(instance_id)
    except XthingsCloudApiError, TimeoutError:
        LOGGER.exception("Failed to unbind Home Assistant during unload")
    await entry.runtime_data.sso_manager.async_revoke_sessions()
    await entry.runtime_data.async_stop_websocket()


async def _async_options_updated(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Apply integration option changes."""
    session = async_get_clientsession(hass)
    client = XthingsCloudApiClient(session, token=entry.data[CONF_TOKEN])
    if entry.options.get(CONF_REMOTE_ACCESS, False):
        await _async_bind_and_enable_remote_access(hass, client)
    else:
        await async_disable_remote_access(hass)
        instance_id = await async_get_instance_id(hass)
        try:
            await client.async_unbind(instance_id)
        except XthingsCloudApiError, TimeoutError:
            LOGGER.exception("FRP stopped, but failed to unbind Home Assistant")


async def _async_bind_and_enable_remote_access(
    hass: HomeAssistant, client: XthingsCloudApiClient
) -> None:
    """Bind this instance before enabling its remote tunnel."""
    instance_id = await async_get_instance_id(hass)
    try:
        owner = await hass.auth.async_get_owner()
        if owner is None:
            raise RuntimeError("Home Assistant owner is not available")
        await client.async_bind(
            instance_id,
            sso_ha_user_id=owner.id,
        )
    except XthingsCloudApiError, TimeoutError:
        await async_disable_remote_access(hass)
        LOGGER.exception("Failed to bind Home Assistant; remote access is stopped")
        return
    await async_enable_remote_access(hass, client, instance_id)
