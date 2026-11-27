"""Remote access management via FRP."""

import asyncio
from pathlib import Path
from typing import Any

import yaml
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from yaml.nodes import MappingNode, ScalarNode

from .const import DOMAIN, LOGGER
from .frp import async_ensure_frpc, build_frpc_toml
from .frp_process import (
    async_start_frpc,
    async_stop_frpc,
    remove_frpc_config,
)
from .ha_xthings_cloud import XthingsCloudApiClient

FRPC_CONFIG_FILENAME = "frpc.toml"


def _get_frp_dir() -> Path:
    """Return the FRP directory inside the component."""
    return Path(__file__).parent / "frp"


def _get_frpc_config_path(hass: HomeAssistant) -> Path:
    """Return the FRP config path in the HA config directory."""
    return Path(hass.config.config_dir) / FRPC_CONFIG_FILENAME


def _get_ha_port(hass: HomeAssistant) -> int:
    """Get the configured Home Assistant HTTP port."""
    http_config = hass.data.get("http")
    if http_config and hasattr(http_config, "server_port"):
        return http_config.server_port
    return 8123


async def _async_stop_frpc(hass: HomeAssistant) -> None:
    """Stop the running FRPC process."""
    process: asyncio.subprocess.Process | None = hass.data.get(f"{DOMAIN}_frpc_process")
    await async_stop_frpc(process)
    hass.data.pop(f"{DOMAIN}_frpc_process", None)


def _get_http_config(content: str) -> dict[str, Any] | None:
    """Return the top-level HTTP config without loading include directives."""
    try:
        root = yaml.compose(content, Loader=yaml.SafeLoader)
    except yaml.YAMLError as err:
        LOGGER.error("Failed to parse configuration.yaml: %s", err)
        return None
    if not isinstance(root, MappingNode):
        return None
    for key, value in root.value:
        if not isinstance(key, ScalarNode) or key.value != "http":
            continue
        if not isinstance(value, MappingNode):
            return None
        try:
            http_config = yaml.safe_load(yaml.serialize(value))
        except yaml.YAMLError as err:
            LOGGER.error("Failed to parse the http configuration: %s", err)
            return None
        return http_config if isinstance(http_config, dict) else None
    return {}


def _ensure_http_proxy_config(hass: HomeAssistant) -> None:
    """Ensure HA trusts the local FRP reverse proxy."""
    config_path = Path(hass.config.config_dir) / "configuration.yaml"
    if not config_path.exists():
        return

    content = config_path.read_text(encoding="utf-8")
    http_config = _get_http_config(content)
    if http_config is None:
        LOGGER.warning(
            "Could not verify http proxy settings; set use_x_forwarded_for: true "
            "and add 127.0.0.1 to http.trusted_proxies"
        )
        return
    if not http_config:
        block = (
            "\n# Auto-configured by Xthings Cloud for remote access\n"
            "http:\n"
            "  use_x_forwarded_for: true\n"
            "  trusted_proxies:\n"
            "    - 127.0.0.1\n"
        )
        config_path.write_text(content.rstrip() + "\n" + block, encoding="utf-8")
        return

    trusted = http_config.get("trusted_proxies")
    if http_config.get("use_x_forwarded_for") is not True or not (
        isinstance(trusted, list) and "127.0.0.1" in trusted
    ):
        LOGGER.warning(
            "http proxy settings are incomplete; set use_x_forwarded_for: true "
            "and add 127.0.0.1 to http.trusted_proxies"
        )


async def async_enable_remote_access(
    hass: HomeAssistant, client: XthingsCloudApiClient, client_id: str
) -> str | None:
    """Fetch cloud FRP settings, write config, and start frpc."""
    await _async_stop_frpc(hass)
    frpc_path = await async_ensure_frpc(async_get_clientsession(hass), _get_frp_dir())
    if not frpc_path:
        return None

    config_path = _get_frpc_config_path(hass)
    try:
        data = await client.async_get_frp_config(client_id)
        await asyncio.to_thread(config_path.parent.mkdir, parents=True, exist_ok=True)
        await asyncio.to_thread(
            config_path.write_text,
            build_frpc_toml(data, _get_ha_port(hass), client_id),
            encoding="utf-8",
        )
    except Exception as err:  # noqa: BLE001
        LOGGER.error("Failed to get or write FRP config: %s", err)
        return None

    await hass.async_add_executor_job(_ensure_http_proxy_config, hass)

    process = await async_start_frpc(frpc_path, config_path)
    if process:
        hass.data[f"{DOMAIN}_frpc_process"] = process

    subdomain = data.get("http", {}).get("subdomain", "")
    if subdomain:
        LOGGER.info("Remote access enabled: https://%s.gw.xthings.com", subdomain)
    return subdomain


async def async_disable_remote_access(hass: HomeAssistant) -> None:
    """Stop frpc and remove its generated configuration."""
    await _async_stop_frpc(hass)
    config_path = _get_frpc_config_path(hass)
    await hass.async_add_executor_job(remove_frpc_config, config_path)
