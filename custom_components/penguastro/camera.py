"""Cached live-stack preview camera for PenguAstro."""

from __future__ import annotations

from homeassistant.components.camera import Camera
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import PenguAstroCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up live-stack preview camera."""
    coordinator: PenguAstroCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([PenguAstroLiveStackCamera(coordinator, entry)])


class PenguAstroLiveStackCamera(CoordinatorEntity[PenguAstroCoordinator], Camera):
    """Camera entity serving the most recently cached stack JPEG."""

    _attr_has_entity_name = True
    _attr_translation_key = "live_stack_preview"
    _attr_icon = "mdi:telescope"
    _attr_is_on = True
    _attr_is_recording = False
    _attr_is_streaming = False

    def __init__(self, coordinator: PenguAstroCoordinator, entry: ConfigEntry) -> None:
        CoordinatorEntity.__init__(self, coordinator)
        Camera.__init__(self)
        device_id = entry.unique_id or entry.entry_id
        self._attr_unique_id = f"{device_id}_live_stack_preview"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device_id)},
            name=entry.title,
            manufacturer="DWARFLAB",
            model="DWARF 3",
            sw_version=entry.data.get("firmware"),
        )

    @property
    def content_type(self) -> str:
        """Return cached image content type."""
        return "image/jpeg"

    async def async_camera_image(
        self, width: int | None = None, height: int | None = None
    ) -> bytes | None:
        """Return cached image without additional device I/O."""
        if self.coordinator.data is None:
            return None
        return self.coordinator.data.image

    @property
    def extra_state_attributes(self) -> dict[str, str]:
        """Expose timestamp of the cached preview."""
        if self.coordinator.data is None or self.coordinator.data.image_updated is None:
            return {}
        return {"last_image_update": self.coordinator.data.image_updated.isoformat()}
