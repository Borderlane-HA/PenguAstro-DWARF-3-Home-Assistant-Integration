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
from homeassistant.const import DEGREE, PERCENTAGE, UnitOfTemperature, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN
from .coordinator import PenguAstroCoordinator
from .entity import PenguAstroEntity


@dataclass(frozen=True, kw_only=True)
class PenguAstroSensorDescription(SensorEntityDescription):
    """PenguAstro sensor description."""

    value_fn: Callable[[PenguAstroCoordinator], Any]


def _status(coordinator: PenguAstroCoordinator):
    return coordinator.data.status if coordinator.data is not None else None


def _progress_value(coordinator: PenguAstroCoordinator, camera: str, attr: str):
    status = _status(coordinator)
    if status is None:
        return None
    progress = status.tele_progress if camera == "tele" else status.wide_progress
    return getattr(progress, attr, None) if progress is not None else None


SENSORS: tuple[PenguAstroSensorDescription, ...] = (
    PenguAstroSensorDescription(
        key="status",
        translation_key="status",
        icon="mdi:telescope",
        value_fn=lambda c: _status(c).activity if _status(c) else None,
    ),
    PenguAstroSensorDescription(
        key="battery",
        translation_key="battery",
        device_class=SensorDeviceClass.BATTERY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda c: _status(c).battery if _status(c) else None,
    ),
    PenguAstroSensorDescription(
        key="shooting_mode",
        translation_key="shooting_mode",
        icon="mdi:camera-iris",
        value_fn=lambda c: _status(c).shooting_mode if _status(c) else None,
    ),
    PenguAstroSensorDescription(
        key="target_name",
        translation_key="target_name",
        icon="mdi:star-four-points",
        value_fn=lambda c: _status(c).target_name if _status(c) else None,
    ),
    PenguAstroSensorDescription(
        key="active_camera",
        translation_key="active_camera",
        icon="mdi:camera",
        value_fn=lambda c: _status(c).active_camera if _status(c) else None,
    ),
    PenguAstroSensorDescription(
        key="session_duration",
        translation_key="session_duration",
        icon="mdi:timer-outline",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda c: c.data.session_duration if c.data else None,
    ),
    PenguAstroSensorDescription(
        key="tele_stacking",
        translation_key="tele_stacking",
        icon="mdi:image-multiple",
        value_fn=lambda c: _status(c).tele_stacking if _status(c) else None,
    ),
    PenguAstroSensorDescription(
        key="wide_stacking",
        translation_key="wide_stacking",
        icon="mdi:image-multiple-outline",
        value_fn=lambda c: _status(c).wide_stacking if _status(c) else None,
    ),
    PenguAstroSensorDescription(
        key="tele_stack_frames",
        translation_key="tele_stack_frames",
        icon="mdi:counter",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda c: _progress_value(c, "tele", "current_count"),
    ),
    PenguAstroSensorDescription(
        key="tele_stack_target_frames",
        translation_key="tele_stack_target_frames",
        icon="mdi:target",
        value_fn=lambda c: _progress_value(c, "tele", "total_count"),
    ),
    PenguAstroSensorDescription(
        key="tele_stack_shooting_time",
        translation_key="tele_stack_shooting_time",
        icon="mdi:timer-sand",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda c: _progress_value(c, "tele", "shooting_time"),
    ),
    PenguAstroSensorDescription(
        key="wide_stack_frames",
        translation_key="wide_stack_frames",
        icon="mdi:counter",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda c: _progress_value(c, "wide", "current_count"),
    ),
    PenguAstroSensorDescription(
        key="wide_stack_target_frames",
        translation_key="wide_stack_target_frames",
        icon="mdi:target",
        value_fn=lambda c: _progress_value(c, "wide", "total_count"),
    ),
    PenguAstroSensorDescription(
        key="wide_stack_shooting_time",
        translation_key="wide_stack_shooting_time",
        icon="mdi:timer-sand",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda c: _progress_value(c, "wide", "shooting_time"),
    ),
    PenguAstroSensorDescription(
        key="temperature",
        translation_key="temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda c: _status(c).temperature if _status(c) else None,
    ),
    PenguAstroSensorDescription(
        key="tele_cmos_temperature",
        translation_key="tele_cmos_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda c: _status(c).tele_cmos_temperature if _status(c) else None,
    ),
    PenguAstroSensorDescription(
        key="wide_cmos_temperature",
        translation_key="wide_cmos_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda c: _status(c).wide_cmos_temperature if _status(c) else None,
    ),
    PenguAstroSensorDescription(
        key="storage_available",
        translation_key="storage_available",
        icon="mdi:sd",
        native_unit_of_measurement="GB",
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda c: _status(c).storage_available if _status(c) else None,
    ),
    PenguAstroSensorDescription(
        key="storage_total",
        translation_key="storage_total",
        icon="mdi:sd",
        native_unit_of_measurement="GB",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda c: _status(c).storage_total if _status(c) else None,
    ),
    PenguAstroSensorDescription(
        key="storage_used_percent",
        translation_key="storage_used_percent",
        icon="mdi:harddisk",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda c: _status(c).storage_used_percent if _status(c) else None,
    ),
    PenguAstroSensorDescription(
        key="focus_position",
        translation_key="focus_position",
        icon="mdi:focus-auto",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda c: _status(c).focus_position if _status(c) else None,
    ),
    PenguAstroSensorDescription(
        key="body_mode",
        translation_key="body_mode",
        icon="mdi:axis-arrow",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda c: _status(c).body_mode if _status(c) else None,
    ),
    PenguAstroSensorDescription(
        key="calibration_azimuth",
        translation_key="calibration_azimuth",
        icon="mdi:compass",
        native_unit_of_measurement=DEGREE,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda c: _status(c).calibration_azimuth if _status(c) else None,
    ),
    PenguAstroSensorDescription(
        key="calibration_altitude",
        translation_key="calibration_altitude",
        icon="mdi:angle-acute",
        native_unit_of_measurement=DEGREE,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda c: _status(c).calibration_altitude if _status(c) else None,
    ),
    PenguAstroSensorDescription(
        key="last_seen",
        translation_key="last_seen",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda c: c.data.status_updated if c.data else None,
    ),
    PenguAstroSensorDescription(
        key="last_stack_image_update",
        translation_key="last_stack_image_update",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda c: c.data.image_updated if c.data else None,
    ),
    PenguAstroSensorDescription(
        key="firmware",
        translation_key="firmware",
        icon="mdi:chip",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda c: c.entry.data.get("firmware"),
    ),
    PenguAstroSensorDescription(
        key="ip_address",
        translation_key="ip_address",
        icon="mdi:ip-network",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda c: c.api.host,
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
        return self.entity_description.value_fn(self.coordinator)
