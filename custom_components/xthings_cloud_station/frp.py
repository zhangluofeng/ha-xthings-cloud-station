"""FRPC download and configuration helpers for Xthings Cloud Station."""

import asyncio
import configparser
import json
import logging
import platform
import stat
from pathlib import Path
from typing import Any

import aiohttp

FRP_BASE_URL = "https://xthings-deploy-package.s3.us-west-2.amazonaws.com/Frp"
FALLBACK_FRPC_VERSION = "0.68.0"
LOGGER = logging.getLogger(__package__)
PLATFORM_MAP = {
    ("Darwin", "arm64"): "darwin_arm64",
    ("Darwin", "x86_64"): "darwin_amd64",
    ("Linux", "aarch64"): "linux_arm64",
    ("Linux", "x86_64"): "linux_amd64",
}


def build_frpc_toml(
    data: dict[str, Any], ha_port: int, client_id: str
) -> str:
    """Build an FRPC TOML configuration from cloud settings."""
    http_config = data.get("http", {})
    lines = [
        f'clientID = "{client_id}"',
        f'serverAddr = "{data.get("serverAddr", "")}"',
        f"serverPort = {data.get('serverPort', 7002)}",
        "loginFailExit = false",
        'auth.method = "token"',
        f'auth.token = "{data.get("auth_token", "")}"',
        f'metadatas.jwt = "{data.get("metadatas_jwt", "")}"',
        "",
        "[transport]",
        f'protocol = "{data.get("transport_protocol", "kcp")}"',
        "",
        "[[proxies]]",
        f'name = "{http_config.get("name", "")}"',
        f'type = "{http_config.get("type", "http")}"',
        'localIP = "127.0.0.1"',
        f"localPort = {ha_port}",
        f'subdomain = "{http_config.get("subdomain", "")}"',
    ]
    request_headers = http_config.get("requestHeaders", {})
    if isinstance(request_headers, dict):
        for name, value in request_headers.get("set", {}).items():
            lines.append(f"requestHeaders.set.{name} = {json.dumps(str(value))}")
    return "\n".join(lines) + "\n"


async def async_ensure_frpc(session: aiohttp.ClientSession, save_dir: Path) -> Path | None:
    """Download the FRPC binary for the current platform if needed."""
    platform_key = PLATFORM_MAP.get((platform.system(), platform.machine()))
    if not platform_key:
        return None
    frp_dir = Path(save_dir)
    binary = frp_dir / platform_key / "frpc"
    try:
        async with session.get(f"{FRP_BASE_URL}/upgrade.ini") as response:
            response.raise_for_status()
            parser = configparser.ConfigParser()
            parser.read_string("[frp]\n" + await response.text())
            version = parser.get("frp", "version").strip('"')
            remote_path = parser.get("frp", platform_key).strip('"')
    except (aiohttp.ClientError, asyncio.TimeoutError, configparser.Error, KeyError):
        if binary.exists():
            LOGGER.warning("FRP upgrade manifest unavailable; using existing binary")
            return binary
        LOGGER.warning("FRP upgrade manifest unavailable; using fallback %s", FALLBACK_FRPC_VERSION)
        version = FALLBACK_FRPC_VERSION
        remote_path = f"{version}/{platform_key}/frpc"
    version_file = frp_dir / "version.txt"
    if binary.exists() and version_file.exists() and version_file.read_text().strip() == version:
        return binary
    try:
        async with session.get(f"{FRP_BASE_URL}/{remote_path}") as response:
            response.raise_for_status()
            content = await response.read()
        binary.parent.mkdir(parents=True, exist_ok=True)
        binary.write_bytes(content)
        binary.chmod(binary.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
        version_file.write_text(version, encoding="utf-8")
    except (aiohttp.ClientError, asyncio.TimeoutError, OSError) as err:
        LOGGER.error("Failed to download FRPC binary: %s", err)
        return binary if binary.exists() else None
    return binary
