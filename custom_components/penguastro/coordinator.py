"""Data coordinator for PenguAstro."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import PenguAstroApi, PenguAstroApiError, PenguAstroData
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

        previous_image = self.data.image if self.data is not None else None
        previous_updated = self.data.image_updated if self.data is not None else None

        # Only touch the stack-image endpoint while stacking is active. This
        # keeps idle polling lightweight and reduces unnecessary device traffic.
        # Image errors never make the status entities unavailable; the camera
        # retains the last successfully fetched live-stack frame.
        stacking_active = (
            status.tele_stacking_state in (1, 2)
            or status.wide_stacking_state in (1, 2)
        )
        image = await self.api.async_get_stack_image() if stacking_active else None
        if image is not None:
            image_updated = datetime.now(UTC)
        else:
            image = previous_image
            image_updated = previous_updated

        return PenguAstroData(status=status, image=image, image_updated=image_updated)
