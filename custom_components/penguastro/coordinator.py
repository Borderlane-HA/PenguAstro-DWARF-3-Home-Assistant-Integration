"""Data coordinator for PenguAstro."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import DeviceStatus, PenguAstroApi, PenguAstroApiError, PenguAstroData
from .const import CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL, DOMAIN

_LOGGER = logging.getLogger(__name__)


class PenguAstroCoordinator(DataUpdateCoordinator[PenguAstroData]):
    """Poll the DWARF 3 with a short-lived status connection."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        api: PenguAstroApi,
    ) -> None:
        self.entry = entry
        self.api = api
        self._session_started: datetime | None = None
        interval = int(entry.options.get(CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL))
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_{entry.entry_id}",
            update_interval=timedelta(seconds=interval),
        )

    async def _async_update_data(self) -> PenguAstroData:
        try:
            status = await self.api.async_get_status()
        except PenguAstroApiError as err:
            raise UpdateFailed(f"Unable to read DWARF 3 status: {err}") from err

        now = datetime.now(UTC)
        previous = self.data
        if previous is not None:
            _carry_stacking_progress(status, previous.status)

        # Track a local session timer across related active operations. This is
        # intentionally a Home Assistant runtime timer rather than a claim that
        # the DWARF exposes a universal session-start timestamp.
        session_active = (
            status.is_imaging
            or status.is_tracking
            or status.is_goto
            or status.is_autofocus
            or status.motion_operation == "Astro calibration"
        )
        if session_active:
            if self._session_started is None:
                self._session_started = now
            session_duration = max(0, int((now - self._session_started).total_seconds()))
        else:
            self._session_started = None
            session_duration = None

        previous_image = previous.image if previous is not None else None
        previous_updated = previous.image_updated if previous is not None else None

        # Only touch the stack-image endpoint while stacking is active. Image
        # errors never make the status entities unavailable; the camera retains
        # the last successfully fetched live-stack frame.
        image = await self.api.async_get_stack_image() if status.is_stacking else None
        if image is not None:
            image_updated = now
        else:
            image = previous_image
            image_updated = previous_updated

        return PenguAstroData(
            status=status,
            status_updated=now,
            session_started=self._session_started,
            session_duration=session_duration,
            image=image,
            image_updated=image_updated,
        )


def _carry_stacking_progress(current: DeviceStatus, previous: DeviceStatus) -> None:
    """Keep the most recent progress while the same camera is still stacking."""
    if current.tele_stacking_state in (1, 2):
        if current.tele_progress is None:
            current.tele_progress = previous.tele_progress
    else:
        current.tele_progress = None

    if current.wide_stacking_state in (1, 2):
        if current.wide_progress is None:
            current.wide_progress = previous.wide_progress
    else:
        current.wide_progress = None

    if current.target_name is None and current.is_stacking:
        for progress in (current.tele_progress, current.wide_progress):
            if progress is not None and progress.target_name:
                current.target_name = progress.target_name
                break
