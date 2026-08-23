"""Diagnostics support for PenguAstro."""

from __future__ import annotations

from dataclasses import asdict

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN, VERSION
from .coordinator import PenguAstroCoordinator


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict:
    """Return sanitized diagnostics for a PenguAstro config entry."""
    coordinator: PenguAstroCoordinator = hass.data[DOMAIN][entry.entry_id]
    data = coordinator.data

    status = _json_safe(asdict(data.status)) if data is not None else None
    # No serial number, BLE identifier, device password or Wi-Fi credentials are
    # ever retained by the integration. The host and MAC are omitted here too,
    # so diagnostics can be shared in public issue reports more safely.
    return {
        "penguastro_version": VERSION,
        "entry_title": entry.title,
        "firmware": entry.data.get("firmware"),
        "update_interval": int(
            entry.options.get("update_interval", coordinator.update_interval.total_seconds())
        ),
        "last_update_success": coordinator.last_update_success,
        "status": status,
        "status_updated": data.status_updated.isoformat()
        if data and data.status_updated
        else None,
        "session_started": data.session_started.isoformat()
        if data and data.session_started
        else None,
        "session_duration": data.session_duration if data else None,
        "stack_image_cached": bool(data and data.image),
        "stack_image_updated": data.image_updated.isoformat()
        if data and data.image_updated
        else None,
    }


def _json_safe(value):
    """Convert datetime values in nested dataclass output to ISO strings."""
    if hasattr(value, "isoformat"):
        return value.isoformat()
    if isinstance(value, dict):
        return {key: _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    return value
