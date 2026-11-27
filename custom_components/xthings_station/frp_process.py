"""FRPC process lifecycle helpers."""

import asyncio
from pathlib import Path


async def async_start_frpc(
    frpc_path: Path, config_path: Path
) -> asyncio.subprocess.Process | None:
    """Start FRPC after checking that its configuration exists."""
    if not config_path.exists():
        return None
    process = await asyncio.create_subprocess_exec(
        str(frpc_path), "-c", str(config_path),
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.DEVNULL,
    )
    return process


async def async_stop_frpc(process: asyncio.subprocess.Process | None) -> None:
    """Stop a running FRPC process."""
    if process is None or process.returncode is not None:
        return
    process.terminate()
    try:
        await asyncio.wait_for(process.wait(), timeout=5)
    except TimeoutError:
        process.kill()
        await process.wait()


def remove_frpc_config(config_path: Path) -> None:
    """Remove a generated FRPC configuration."""
    config_path.unlink(missing_ok=True)
