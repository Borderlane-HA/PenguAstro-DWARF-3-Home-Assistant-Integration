"""Binary sensor platform for PenguAstro."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN
from .coordinator import PenguAstroCoordinator
from .entity import PenguAstroEntity


@dataclass(frozen=True, kw_only=True)
class PenguAstroBinarySensorDescription(BinarySensorEntityDescription):
    """PenguAstro binary sensor description."""

    value_fn: Callable[[PenguAstroCoordinator], bool | None]


def _status(coordinator: PenguAstroCoordinator):
    return coordinator.data.status if coordinator.data is not None else None


BINARY_SENSORS: tuple[PenguAstroBinarySensorDescription, ...] = (
    PenguAstroBinarySensorDescription(
        key="connected",
        translation_key="connected",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        value_fn=lambda c: c.last_update_success,
    ),
    PenguAstroBinarySensorDescription(
        key="imaging",
        translation_key="imaging",
        icon="mdi:camera",
        value_fn=lambda c: _status(c).is_imaging if _status(c) else None,
    ),
    PenguAstroBinarySensorDescription(
        key="stacking",
        translation_key="stacking",
        icon="mdi:image-multiple",
        value_fn=lambda c: _status(c).is_stacking if _status(c) else None,
    ),
    PenguAstroBinarySensorDescription(
        key="tracking",
        translation_key="tracking",
        icon="mdi:crosshairs-gps",
        value_fn=lambda c: _status(c).is_tracking if _status(c) else None,
    ),
    PenguAstroBinarySensorDescription(
        key="goto",
        translation_key="goto",
        icon="mdi:target",
        value_fn=lambda c: _status(c).is_goto if _status(c) else None,
    ),
    PenguAstroBinarySensorDescription(
        key="autofocus",
        translation_key="autofocus",
        icon="mdi:focus-auto",
        value_fn=lambda c: _status(c).is_autofocus if _status(c) else None,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up PenguAstro binary sensors."""
    coordinator: PenguAstroCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        PenguAstroBinarySensor(coordinator, entry, description)
        for description in BINARY_SENSORS
    )


class PenguAstroBinarySensor(PenguAstroEntity, BinarySensorEntity):
    """One PenguAstro binary sensor."""

    entity_description: PenguAstroBinarySensorDescription

    def __init__(
        self,
        coordinator: PenguAstroCoordinator,
        entry: ConfigEntry,
        description: PenguAstroBinarySensorDescription,
    ) -> None:
        super().__init__(coordinator, entry)
        self.entity_description = description
        self._attr_unique_id = f"{entry.unique_id or entry.entry_id}_{description.key}"

    @property
    def is_on(self) -> bool | None:
        """Return whether the condition is active."""
        return self.entity_description.value_fn(self.coordinator)

    @property
    def available(self) -> bool:
        """Keep connectivity sensor useful during communication failures."""
        if self.entity_description.key == "connected":
            return True
        return super().available
