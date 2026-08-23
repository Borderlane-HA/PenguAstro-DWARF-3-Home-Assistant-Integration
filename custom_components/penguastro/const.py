"""Constants for PenguAstro."""

from typing import Final

DOMAIN: Final = "penguastro"
NAME: Final = "PenguAstro"
VERSION: Final = "0.1.2"

CONF_UPDATE_INTERVAL: Final = "update_interval"
DEFAULT_UPDATE_INTERVAL: Final = 60
MIN_UPDATE_INTERVAL: Final = 30
MAX_UPDATE_INTERVAL: Final = 3600

HTTP_PORT: Final = 8082
STACK_IMAGE_PORT: Final = 8092
WS_PORT: Final = 9900

PLATFORMS: Final = ["sensor", "camera"]

SHOOTING_MODES: Final[dict[int, str]] = {
    1: "Normal",
    2: "DSO",
    3: "Sun/Moon",
    4: "Milky Way",
    5: "Star Trail",
    6: "Auto Tracking",
    7: "Panorama",
    8: "Sun",
    9: "Moon",
    10: "Planet",
}

OPERATION_STATES: Final[dict[int, str]] = {
    0: "idle",
    1: "running",
    2: "stopping",
    3: "stopped",
}
