"""Sensor platform for PenguAstro."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .api import DeviceStatus
from .const import DOMAIN
from .coordinator import PenguAstroCoordinator
from .entity import PenguAstroEntity


@dataclass(frozen=True, kw_only=True)
class PenguAstroSensorDescription(SensorEntityDescription):
    """PenguAstro sensor description."""

    value_fn: Callable[[DeviceStatus], Any]


SENSORS: tuple[PenguAstroSensorDescription, ...] = (
    PenguAstroSensorDescription(
        key="status",
        translation_key="status",
        icon="mdi:telescope",
        value_fn=lambda s: s.activity,
    ),
    PenguAstroSensorDescription(
        key="battery",
        translation_key="battery",
        device_class=SensorDeviceClass.BATTERY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda s: s.battery,
    ),
    PenguAstroSensorDescription(
        key="shooting_mode",
        translation_key="shooting_mode",
        icon="mdi:camera-iris",
        value_fn=lambda s: s.shooting_mode,
    ),
    PenguAstroSensorDescription(
        key="tele_stacking",
        translation_key="tele_stacking",
        icon="mdi:image-multiple",
        value_fn=lambda s: s.tele_stacking,
    ),
    PenguAstroSensorDescription(
        key="wide_stacking",
        translation_key="wide_stacking",
        icon="mdi:image-multiple-outline",
        value_fn=lambda s: s.wide_stacking,
    ),
    PenguAstroSensorDescription(
        key="temperature",
        translation_key="temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda s: s.temperature,
    ),
    PenguAstroSensorDescription(
        key="tele_cmos_temperature",
        translation_key="tele_cmos_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda s: s.tele_cmos_temperature,
    ),
    PenguAstroSensorDescription(
        key="wide_cmos_temperature",
        translation_key="wide_cmos_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda s: s.wide_cmos_temperature,
    ),
    PenguAstroSensorDescription(
        key="storage_available",
        translation_key="storage_available",
        icon="mdi:sd",
        native_unit_of_measurement="GB",
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda s: s.storage_available,
    ),
    PenguAstroSensorDescription(
        key="storage_total",
        translation_key="storage_total",
        icon="mdi:sd",
        native_unit_of_measurement="GB",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda s: s.storage_total,
    ),
    PenguAstroSensorDescription(
        key="focus_position",
        translation_key="focus_position",
        icon="mdi:focus-auto",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda s: s.focus_position,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up sensors."""
    coordinator: PenguAstroCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        PenguAstroSensor(coordinator, entry, description) for description in SENSORS
    )


class PenguAstroSensor(PenguAstroEntity, SensorEntity):
    """One PenguAstro sensor."""

    entity_description: PenguAstroSensorDescription

    def __init__(
        self,
        coordinator: PenguAstroCoordinator,
        entry: ConfigEntry,
        description: PenguAstroSensorDescription,
    ) -> None:
        super().__init__(coordinator, entry)
        self.entity_description = description
        self._attr_unique_id = f"{entry.unique_id or entry.entry_id}_{description.key}"

    @property
    def native_value(self) -> Any:
        """Return sensor value."""
        if self.coordinator.data is None:
            return None
        return self.entity_description.value_fn(self.coordinator.data.status)
