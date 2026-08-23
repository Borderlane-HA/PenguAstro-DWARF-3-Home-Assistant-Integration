"""Camera entities for PenguAstro."""

from __future__ import annotations

from homeassistant.components.camera import Camera, CameraEntityFeature
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
    """Set up PenguAstro camera entities."""
    coordinator: PenguAstroCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            PenguAstroLiveStackCamera(coordinator, entry),
            PenguAstroRTSPCamera(coordinator, entry, "tele_live", 0),
            PenguAstroRTSPCamera(coordinator, entry, "wide_live", 1),
        ]
    )


class PenguAstroCameraBase(CoordinatorEntity[PenguAstroCoordinator], Camera):
    """Shared base class for PenguAstro camera entities."""

    _attr_has_entity_name = True
    _attr_is_on = True
    _attr_is_recording = False

    def __init__(
        self,
        coordinator: PenguAstroCoordinator,
        entry: ConfigEntry,
        unique_suffix: str,
    ) -> None:
        CoordinatorEntity.__init__(self, coordinator)
        Camera.__init__(self)
        device_id = entry.unique_id or entry.entry_id
        self._attr_unique_id = f"{device_id}_{unique_suffix}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device_id)},
            name=entry.title,
            manufacturer="DWARFLAB",
            model="DWARF 3",
            sw_version=entry.data.get("firmware"),
        )


class PenguAstroLiveStackCamera(PenguAstroCameraBase):
    """Camera entity serving the most recently cached stack JPEG."""

    _attr_translation_key = "live_stack_preview"
    _attr_icon = "mdi:telescope"
    _attr_is_streaming = False

    def __init__(self, coordinator: PenguAstroCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry, "live_stack_preview")

    async def async_camera_image(
        self, width: int | None = None, height: int | None = None
    ) -> bytes | None:
        """Return cached image without additional device I/O."""
        if self.coordinator.data is None:
            return None
        return self.coordinator.data.image

    @property
    def extra_state_attributes(self) -> dict[str, object]:
        """Expose useful dashboard metadata for the cached preview."""
        if self.coordinator.data is None:
            return {}

        data = self.coordinator.data
        status = data.status
        attrs: dict[str, object] = {
            "activity": status.activity,
            "target": status.target_name,
            "active_camera": status.active_camera,
        }
        if data.image_updated is not None:
            attrs["last_image_update"] = data.image_updated.isoformat()

        if status.tele_stacking_state in (1, 2) and status.tele_progress is not None:
            attrs["current_frames"] = status.tele_progress.current_count
            attrs["target_frames"] = status.tele_progress.total_count
            attrs["stack_camera"] = "Tele"
        elif status.wide_stacking_state in (1, 2) and status.wide_progress is not None:
            attrs["current_frames"] = status.wide_progress.current_count
            attrs["target_frames"] = status.wide_progress.total_count
            attrs["stack_camera"] = "Wide"

        return {key: value for key, value in attrs.items() if value is not None}


class PenguAstroRTSPCamera(PenguAstroCameraBase):
    """On-demand RTSP camera for the DWARF 3 tele or wide lens."""

    _attr_supported_features = CameraEntityFeature.STREAM
    _attr_icon = "mdi:video"

    def __init__(
        self,
        coordinator: PenguAstroCoordinator,
        entry: ConfigEntry,
        translation_key: str,
        channel: int,
    ) -> None:
        super().__init__(coordinator, entry, translation_key)
        self._attr_translation_key = translation_key
        self._channel = channel

    @property
    def use_stream_for_stills(self) -> bool:
        """Generate still previews from the RTSP stream when requested."""
        return True

    async def stream_source(self) -> str | None:
        """Return the local DWARF 3 RTSP source."""
        host = self.coordinator.api.host
        if ":" in host and not host.startswith("["):
            host = f"[{host}]"
        return f"rtsp://{host}/ch{self._channel}/stream0"
