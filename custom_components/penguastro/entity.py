"""Base entities for PenguAstro."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import PenguAstroCoordinator


class PenguAstroEntity(CoordinatorEntity[PenguAstroCoordinator]):
    """Base coordinator entity."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: PenguAstroCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._entry = entry
        device_id = entry.unique_id or entry.entry_id
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device_id)},
            name=entry.title,
            manufacturer="DWARFLAB",
            model="DWARF 3",
            sw_version=entry.data.get("firmware")
        )
