"""Local network client for a DWARFLAB DWARF 3.

PenguAstro deliberately uses read-only HTTP/WebSocket requests. It never
acquires a master lock and never sends motor, camera, focus or capture-control
commands.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import UTC, datetime
import logging
import secrets
import struct
from typing import Any

from aiohttp import ClientError, ClientSession, ClientTimeout, WSMsgType

from .const import HTTP_PORT, OPERATION_STATES, SHOOTING_MODES, STACK_IMAGE_PORT, WS_PORT

_LOGGER = logging.getLogger(__name__)

# DWARF WebSocket protocol values verified against the community SDK.
_PROTOCOL_MAJOR = 1
_PROTOCOL_MINOR = 20
_DEVICE_ID = 1
_MODULE_TASK_CENTER = 14
_CMD_GET_DEVICE_STATE_INFO = 16405
_CMD_STACKING_PROGRESS = 15209
_MSG_REQUEST = 0
_MSG_RESPONSE_TYPES = {1, 3}

_MAX_IMAGE_BYTES = 16 * 1024 * 1024


class PenguAstroApiError(Exception):
    """Base API error."""


class PenguAstroConnectionError(PenguAstroApiError):
    """Connection to the telescope failed."""


class PenguAstroProtocolError(PenguAstroApiError):
    """The telescope returned an unexpected protocol response."""


@dataclass(slots=True)
class DeviceMetadata:
    """Safe subset of device metadata."""

    name: str
    mac: str | None
    firmware: str | None


@dataclass(slots=True)
class StackProgress:
    """Best-effort live-stacking progress seen during a short status poll."""

    total_count: int | None = None
    current_count: int | None = None
    exp_index: int | None = None
    gain_index: int | None = None
    target_name: str | None = None
    shooting_time: int | None = None
    stacked_time: int | None = None
    observed_at: datetime | None = None

    def merge(self, other: "StackProgress") -> None:
        """Merge a partial notification into this progress snapshot."""
        for field_name in (
            "total_count",
            "current_count",
            "exp_index",
            "gain_index",
            "target_name",
            "shooting_time",
            "stacked_time",
            "observed_at",
        ):
            value = getattr(other, field_name)
            if value is not None:
                setattr(self, field_name, value)


@dataclass(slots=True)
class DeviceStatus:
    """Read-only snapshot from command 16405 plus opportunistic notifications."""

    battery: int | None = None
    charging_state: int | None = None
    temperature: int | None = None
    tele_cmos_temperature: int | None = None
    wide_cmos_temperature: int | None = None
    storage_available: int | None = None
    storage_total: int | None = None
    storage_used_percent: float | None = None
    focus_position: int | None = None
    shooting_mode_id: int | None = None
    shooting_mode: str | None = None
    tele_stacking_state: int = 0
    wide_stacking_state: int = 0
    tele_stacking: str = "idle"
    wide_stacking: str = "idle"
    tele_operation: str | None = None
    wide_operation: str | None = None
    focus_operation: str | None = None
    focus_state: int | None = None
    motion_operation: str | None = None
    motion_state: int | None = None
    target_name: str | None = None
    active_camera: str | None = None
    body_mode: str | None = None
    calibration_azimuth: float | None = None
    calibration_altitude: float | None = None
    is_imaging: bool = False
    is_stacking: bool = False
    is_tracking: bool = False
    is_goto: bool = False
    is_autofocus: bool = False
    activity: str = "Idle"
    tele_progress: StackProgress | None = None
    wide_progress: StackProgress | None = None


@dataclass(slots=True)
class PenguAstroData:
    """Coordinator payload."""

    status: DeviceStatus
    status_updated: datetime | None = None
    session_started: datetime | None = None
    session_duration: int | None = None
    image: bytes | None = None
    image_updated: datetime | None = None


def normalize_host(host: str) -> str:
    """Normalize an IP/hostname entered in the UI."""
    value = host.strip()
    for prefix in ("http://", "https://", "ws://", "wss://"):
        if value.lower().startswith(prefix):
            value = value[len(prefix) :]
            break
    return value.strip().strip("/")


def _url_host(host: str) -> str:
    """Wrap IPv6 literals for URL use."""
    if ":" in host and not host.startswith("["):
        return f"[{host}]"
    return host


class PenguAstroApi:
    """Read-only DWARF 3 local API client."""

    def __init__(self, session: ClientSession, host: str) -> None:
        self._session = session
        self.host = normalize_host(host)

    async def async_get_metadata(self) -> DeviceMetadata:
        """Read safe device metadata without retaining sensitive fields."""
        host = _url_host(self.host)
        timeout = ClientTimeout(total=5)
        try:
            async with self._session.post(
                f"http://{host}:{HTTP_PORT}/deviceInfo", timeout=timeout
            ) as response:
                if response.status != 200:
                    raise PenguAstroConnectionError(
                        f"deviceInfo returned HTTP {response.status}"
                    )
                payload = await response.json(content_type=None)
        except (ClientError, asyncio.TimeoutError, ValueError) as err:
            raise PenguAstroConnectionError(str(err)) from err

        data = payload.get("data") if isinstance(payload, dict) else None
        if not isinstance(data, dict):
            raise PenguAstroProtocolError("Invalid /deviceInfo response")

        name = str(data.get("deviceName") or "DWARF 3")
        if "DWARF3" not in name.upper().replace(" ", "") and "DWARF_MINI" not in name.upper().replace(" ", ""):
            raise PenguAstroProtocolError("The device does not identify as DWARF 3 or DWARF mini")

        # Deliberately do NOT keep/log devicePwd, staWifiPwd, SN or BLE service IDs.
        mac_raw = data.get("macAddress") or data.get("mac")
        mac = _normalize_mac(str(mac_raw)) if mac_raw else None

        firmware: str | None = None
        try:
            async with self._session.get(
                f"http://{host}:{HTTP_PORT}/getDefaultParamsConfig", timeout=timeout
            ) as response:
                if response.status == 200:
                    fw_payload = await response.json(content_type=None)
                    fw_data = (
                        fw_payload.get("data", {}) if isinstance(fw_payload, dict) else {}
                    )
                    if isinstance(fw_data, dict):
                        parts = (
                            fw_data.get("fwMajorVersion"),
                            fw_data.get("fwMinorVersion"),
                            fw_data.get("fwPatchVersion"),
                        )
                        if all(isinstance(part, int) for part in parts):
                            firmware = ".".join(str(part) for part in parts)
        except (ClientError, asyncio.TimeoutError, ValueError):
            # Firmware is optional metadata; deviceInfo already validated the host.
            pass

        return DeviceMetadata(name=name, mac=mac, firmware=firmware)

    async def async_get_status(self) -> DeviceStatus:
        """Read one status snapshot over a short-lived WebSocket.

        While waiting for the command-16405 response, the DWARF may push live
        stacking notifications. PenguAstro opportunistically decodes command
        15209 if it arrives naturally; the connection is not held open waiting
        for it. This preserves the short-lived connection model used to reduce
        interference with the official app.
        """
        host = _url_host(self.host)
        client_id = f"ha_{secrets.token_hex(5)}"
        packet = _build_state_request(client_id)
        progress: dict[str, StackProgress] = {}

        try:
            async with asyncio.timeout(6):
                async with self._session.ws_connect(
                    f"ws://{host}:{WS_PORT}",
                    autoping=True,
                    heartbeat=None,
                    max_msg_size=2 * 1024 * 1024,
                ) as ws:
                    await ws.send_bytes(packet)
                    while True:
                        msg = await ws.receive()
                        if msg.type == WSMsgType.BINARY:
                            envelope = _parse_ws_packet(bytes(msg.data))
                            cmd = envelope.get("cmd")
                            payload = envelope.get("data")

                            if cmd == _CMD_STACKING_PROGRESS and isinstance(payload, bytes):
                                camera, update = _parse_stacking_progress(payload)
                                if camera is not None and update is not None:
                                    existing = progress.setdefault(camera, StackProgress())
                                    existing.merge(update)
                                continue

                            if (
                                cmd == _CMD_GET_DEVICE_STATE_INFO
                                and envelope.get("type") in _MSG_RESPONSE_TYPES
                                and isinstance(payload, bytes)
                            ):
                                status = _parse_device_status(payload)
                                status.tele_progress = progress.get("tele")
                                status.wide_progress = progress.get("wide")
                                if status.target_name is None:
                                    status.target_name = _progress_target(status)
                                return status
                        elif msg.type in {
                            WSMsgType.CLOSED,
                            WSMsgType.CLOSE,
                            WSMsgType.CLOSING,
                            WSMsgType.ERROR,
                        }:
                            raise PenguAstroConnectionError(
                                "WebSocket closed before status response"
                            )
        except (ClientError, asyncio.TimeoutError, OSError) as err:
            raise PenguAstroConnectionError(str(err)) from err

    async def async_get_stack_image(self) -> bytes | None:
        """Fetch one JPEG frame from the live-stack HTTP stream.

        The endpoint may be a direct JPEG or a multipart/continuous stream. The
        method reads only until the first complete JPEG is found, then closes.
        """
        host = _url_host(self.host)
        timeout = ClientTimeout(total=6, sock_connect=2, sock_read=4)
        try:
            async with self._session.get(
                f"http://{host}:{STACK_IMAGE_PORT}/mainstream", timeout=timeout
            ) as response:
                if response.status != 200:
                    return None

                buffer = bytearray()
                async for chunk in response.content.iter_chunked(64 * 1024):
                    if not chunk:
                        break
                    buffer.extend(chunk)
                    if len(buffer) > _MAX_IMAGE_BYTES:
                        return None

                    image = _extract_jpeg(buffer)
                    if image is not None:
                        return image

                return _extract_jpeg(buffer)
        except (ClientError, asyncio.TimeoutError, OSError):
            return None


def _normalize_mac(value: str) -> str:
    chars = "".join(ch for ch in value.upper() if ch in "0123456789ABCDEF")
    if len(chars) == 12:
        return ":".join(chars[i : i + 2] for i in range(0, 12, 2))
    return value.upper()


def _encode_varint(value: int) -> bytes:
    if value < 0:
        value &= (1 << 64) - 1
    out = bytearray()
    while True:
        byte = value & 0x7F
        value >>= 7
        if value:
            out.append(byte | 0x80)
        else:
            out.append(byte)
            return bytes(out)


def _field_varint(number: int, value: int) -> bytes:
    return _encode_varint((number << 3) | 0) + _encode_varint(value)


def _field_bytes(number: int, value: bytes) -> bytes:
    return _encode_varint((number << 3) | 2) + _encode_varint(len(value)) + value


def _build_state_request(client_id: str) -> bytes:
    return b"".join(
        (
            _field_varint(1, _PROTOCOL_MAJOR),
            _field_varint(2, _PROTOCOL_MINOR),
            _field_varint(3, _DEVICE_ID),
            _field_varint(4, _MODULE_TASK_CENTER),
            _field_varint(5, _CMD_GET_DEVICE_STATE_INFO),
            _field_varint(6, _MSG_REQUEST),
            _field_bytes(7, b""),
            _field_bytes(8, client_id.encode()),
        )
    )


def _read_varint(data: bytes, offset: int) -> tuple[int, int]:
    result = 0
    shift = 0
    while offset < len(data):
        byte = data[offset]
        offset += 1
        result |= (byte & 0x7F) << shift
        if not byte & 0x80:
            return result, offset
        shift += 7
        if shift > 70:
            raise PenguAstroProtocolError("Invalid protobuf varint")
    raise PenguAstroProtocolError("Truncated protobuf varint")


def _decode_fields(data: bytes) -> dict[int, list[int | bytes]]:
    fields: dict[int, list[int | bytes]] = {}
    offset = 0
    while offset < len(data):
        key, offset = _read_varint(data, offset)
        number = key >> 3
        wire = key & 0x07
        if number == 0:
            raise PenguAstroProtocolError("Invalid protobuf field number")

        if wire == 0:
            value, offset = _read_varint(data, offset)
        elif wire == 1:
            if offset + 8 > len(data):
                raise PenguAstroProtocolError("Truncated fixed64")
            value = data[offset : offset + 8]
            offset += 8
        elif wire == 2:
            length, offset = _read_varint(data, offset)
            end = offset + length
            if end > len(data):
                raise PenguAstroProtocolError("Truncated bytes field")
            value = data[offset:end]
            offset = end
        elif wire == 5:
            if offset + 4 > len(data):
                raise PenguAstroProtocolError("Truncated fixed32")
            value = data[offset : offset + 4]
            offset += 4
        else:
            raise PenguAstroProtocolError(f"Unsupported protobuf wire type {wire}")

        fields.setdefault(number, []).append(value)
    return fields


def _last_varint(fields: dict[int, list[int | bytes]], number: int) -> int | None:
    values = fields.get(number)
    if not values:
        return None
    value = values[-1]
    return value if isinstance(value, int) else None


def _last_bytes(fields: dict[int, list[int | bytes]], number: int) -> bytes | None:
    values = fields.get(number)
    if not values:
        return None
    value = values[-1]
    return value if isinstance(value, bytes) else None


def _last_string(fields: dict[int, list[int | bytes]], number: int) -> str | None:
    value = _last_bytes(fields, number)
    if value is None:
        return None
    try:
        text = value.decode("utf-8").strip()
    except UnicodeDecodeError:
        return None
    return text or None


def _last_double(fields: dict[int, list[int | bytes]], number: int) -> float | None:
    value = _last_bytes(fields, number)
    if value is None or len(value) != 8:
        return None
    return struct.unpack("<d", value)[0]


def _nested(fields: dict[int, list[int | bytes]], number: int) -> dict[int, list[int | bytes]]:
    value = _last_bytes(fields, number)
    return _decode_fields(value) if value is not None else {}


def _parse_ws_packet(data: bytes) -> dict[str, Any]:
    fields = _decode_fields(data)
    return {
        "major": _last_varint(fields, 1),
        "minor": _last_varint(fields, 2),
        "device_id": _last_varint(fields, 3),
        "module": _last_varint(fields, 4),
        "cmd": _last_varint(fields, 5),
        "type": _last_varint(fields, 6),
        "data": _last_bytes(fields, 7) or b"",
    }


def _operation_state(message: dict[int, list[int | bytes]]) -> int:
    state = _last_varint(message, 1)
    return 0 if state is None else state


def _state_label(state: int) -> str:
    return OPERATION_STATES.get(state, f"unknown_{state}")


def _as_int32(value: int | None) -> int | None:
    """Interpret a protobuf int32 value, including negative temperatures."""
    if value is None:
        return None
    value &= 0xFFFFFFFF
    return value - 0x100000000 if value & 0x80000000 else value


def _is_active(state: int | None) -> bool:
    # OperationState uses 1/2 for running/stopping. AstroState additionally
    # uses 4 for plate solving, which is also an active operation.
    return state in (1, 2, 4)


def _camera_details(camera_data: bytes | None) -> dict[str, Any]:
    if camera_data is None:
        return {"cmos": None, "states": {}, "stacking": 0, "operation": None}
    fields = _decode_fields(camera_data)
    cmos_fields = _nested(fields, 7)
    cmos = _as_int32(_last_varint(cmos_fields, 1))

    exclusive = _nested(fields, 1)
    names = {
        1: "stacking",
        2: "photo",
        3: "burst",
        4: "recording",
        5: "timelapse",
        6: "calibration_frame",
        7: "panorama",
        8: "sentry",
    }
    states: dict[str, int] = {}
    operation: str | None = None
    for field_no, name in names.items():
        raw = _last_bytes(exclusive, field_no)
        if raw is not None:
            state = _operation_state(_decode_fields(raw))
            states[name] = state
            if operation is None and _is_active(state):
                operation = name

    stacking = states.get("stacking", 0)
    return {"cmos": cmos, "states": states, "stacking": stacking, "operation": operation}


def _focus_details(payload: bytes | None) -> tuple[str | None, int | None, int | None]:
    if payload is None:
        return None, None, None
    outer = _decode_fields(payload)
    exclusive = _nested(outer, 1)
    mapping = {
        1: "Astro autofocus",
        2: "Autofocus",
        3: "Fast autofocus",
        4: "Area autofocus",
    }
    operation: str | None = None
    operation_state: int | None = None
    for field_no, name in mapping.items():
        raw = _last_bytes(exclusive, field_no)
        if raw is not None:
            state = _operation_state(_decode_fields(raw))
            if _is_active(state):
                operation = name
                operation_state = state
                break
    position = _nested(outer, 2)
    return operation, operation_state, _last_varint(position, 1)


def _state_and_target(raw: bytes | None) -> tuple[int | None, str | None]:
    if raw is None:
        return None, None
    fields = _decode_fields(raw)
    return _last_varint(fields, 1), _last_string(fields, 2)


def _motion_details(payload: bytes | None) -> tuple[str | None, int | None, str | None]:
    if payload is None:
        return None, None, None
    outer = _decode_fields(payload)
    exclusive = _nested(outer, 1)

    simple = {
        1: "Astro calibration",
        2: "GoTo",
        3: "Astro tracking",
        4: "Tracking",
        6: "EQ solving",
        7: "Sentry motion",
        8: "Sky target finder",
    }
    for field_no, name in simple.items():
        raw = _last_bytes(exclusive, field_no)
        if raw is None:
            continue
        state, target = _state_and_target(raw)
        if _is_active(state):
            return name, state, target

    # OneClickGotoState wraps autofocus/calibration/goto/tracking states.
    one_click_raw = _last_bytes(exclusive, 5)
    if one_click_raw is not None:
        one_click = _decode_fields(one_click_raw)
        inner = {
            1: "One-click GoTo: autofocus",
            2: "One-click GoTo: calibration",
            3: "One-click GoTo",
            4: "One-click GoTo: tracking",
        }
        for field_no, name in inner.items():
            raw = _last_bytes(one_click, field_no)
            if raw is None:
                continue
            state, target = _state_and_target(raw)
            if _is_active(state):
                return name, state, target

    return None, None, None


def _derive_activity(
    tele: dict[str, Any],
    wide: dict[str, Any],
    focus_operation: str | None,
    motion_operation: str | None,
) -> str:
    tele_stack = int(tele["stacking"])
    wide_stack = int(wide["stacking"])
    if _is_active(tele_stack) and _is_active(wide_stack):
        return "Live stacking (Tele + Wide)"
    if _is_active(tele_stack):
        return "Live stacking (Tele)"
    if _is_active(wide_stack):
        return "Live stacking (Wide)"

    labels = {
        "recording": "Recording video",
        "timelapse": "Timelapse",
        "photo": "Taking photo",
        "burst": "Burst capture",
        "panorama": "Panorama",
        "calibration_frame": "Calibration frame",
        "sentry": "Sentry",
    }
    for camera_name, camera in (("Tele", tele), ("Wide", wide)):
        operation = camera.get("operation")
        if operation in labels:
            return f"{labels[operation]} ({camera_name})"

    if focus_operation:
        return focus_operation
    if motion_operation:
        return motion_operation
    return "Idle"


def _active_camera(tele: dict[str, Any], wide: dict[str, Any]) -> str | None:
    tele_active = tele.get("operation") is not None
    wide_active = wide.get("operation") is not None
    if tele_active and wide_active:
        return "Tele + Wide"
    if tele_active:
        return "Tele"
    if wide_active:
        return "Wide"
    return None


def _parse_stacking_progress(data: bytes) -> tuple[str | None, StackProgress | None]:
    fields = _decode_fields(data)
    camera_type = _last_varint(fields, 8)
    # camera_type is a proto3 int32, so Tele (0) may be omitted on the wire.
    if camera_type in (None, 0):
        camera = "tele"
    elif camera_type == 1:
        camera = "wide"
    else:
        return None, None

    progress = StackProgress(
        total_count=_last_varint(fields, 1),
        current_count=_last_varint(fields, 3),
        exp_index=_last_varint(fields, 5),
        gain_index=_last_varint(fields, 6),
        target_name=_last_string(fields, 7),
        shooting_time=_last_varint(fields, 9),
        stacked_time=_last_varint(fields, 10),
        observed_at=datetime.now(UTC),
    )
    return camera, progress


def _progress_target(status: DeviceStatus) -> str | None:
    for progress in (status.tele_progress, status.wide_progress):
        if progress is not None and progress.target_name:
            return progress.target_name
    return None


def _parse_device_status(data: bytes) -> DeviceStatus:
    fields = _decode_fields(data)
    code = _last_varint(fields, 7)
    if code is not None and code != 0:
        raise PenguAstroProtocolError(f"DWARF status command returned code {code}")

    shooting_mode_id = _last_varint(fields, 1)
    tele_raw = _last_bytes(fields, 2)
    wide_raw = _last_bytes(fields, 3)
    focus_raw = _last_bytes(fields, 4)
    motion_raw = _last_bytes(fields, 5)
    device_raw = _last_bytes(fields, 6)

    tele = _camera_details(tele_raw)
    wide = _camera_details(wide_raw)
    focus_operation, focus_state, focus_position = _focus_details(focus_raw)
    motion_operation, motion_state, target_name = _motion_details(motion_raw)

    battery = charging_state = temperature = storage_available = storage_total = None
    body_mode: str | None = None
    calibration_azimuth = calibration_altitude = None
    if device_raw is not None:
        device = _decode_fields(device_raw)
        charging = _nested(device, 3)
        storage = _nested(device, 4)
        temp = _nested(device, 7)
        body = _nested(device, 8)
        battery_info = _nested(device, 9)
        calibration = _nested(device, 10)

        charging_state = _last_varint(charging, 1)
        storage_available = _last_varint(storage, 1)
        storage_total = _last_varint(storage, 2)
        temperature = _as_int32(_last_varint(temp, 2))
        battery = _last_varint(battery_info, 1)
        body_value = _last_varint(body, 1)
        body_mode = {0: "Unknown", 1: "EQ", 2: "Alt-Az"}.get(body_value)
        calibration_azimuth = _last_double(calibration, 1)
        calibration_altitude = _last_double(calibration, 2)

    storage_used_percent: float | None = None
    if storage_total and storage_available is not None and storage_total > 0:
        storage_used_percent = round(
            max(0.0, min(100.0, (storage_total - storage_available) / storage_total * 100)),
            1,
        )

    tele_stacking_state = int(tele["stacking"])
    wide_stacking_state = int(wide["stacking"])
    is_stacking = _is_active(tele_stacking_state) or _is_active(wide_stacking_state)
    is_tracking = motion_operation in {"Astro tracking", "Tracking", "One-click GoTo: tracking"}
    is_goto = motion_operation in {"GoTo", "One-click GoTo"}
    is_autofocus = focus_operation is not None or motion_operation == "One-click GoTo: autofocus"
    is_imaging = is_stacking or tele.get("operation") in {
        "photo",
        "burst",
        "recording",
        "timelapse",
        "calibration_frame",
        "panorama",
    } or wide.get("operation") in {
        "photo",
        "burst",
        "recording",
        "timelapse",
        "calibration_frame",
        "panorama",
    }

    return DeviceStatus(
        battery=battery,
        charging_state=charging_state,
        temperature=temperature,
        tele_cmos_temperature=tele["cmos"],
        wide_cmos_temperature=wide["cmos"],
        storage_available=storage_available,
        storage_total=storage_total,
        storage_used_percent=storage_used_percent,
        focus_position=focus_position,
        shooting_mode_id=shooting_mode_id,
        shooting_mode=SHOOTING_MODES.get(shooting_mode_id, str(shooting_mode_id))
        if shooting_mode_id is not None
        else None,
        tele_stacking_state=tele_stacking_state,
        wide_stacking_state=wide_stacking_state,
        tele_stacking=_state_label(tele_stacking_state),
        wide_stacking=_state_label(wide_stacking_state),
        tele_operation=tele.get("operation"),
        wide_operation=wide.get("operation"),
        focus_operation=focus_operation,
        focus_state=focus_state,
        motion_operation=motion_operation,
        motion_state=motion_state,
        target_name=target_name,
        active_camera=_active_camera(tele, wide),
        body_mode=body_mode,
        calibration_azimuth=calibration_azimuth,
        calibration_altitude=calibration_altitude,
        is_imaging=bool(is_imaging),
        is_stacking=is_stacking,
        is_tracking=is_tracking,
        is_goto=is_goto,
        is_autofocus=is_autofocus,
        activity=_derive_activity(tele, wide, focus_operation, motion_operation),
    )


def _extract_jpeg(buffer: bytes | bytearray) -> bytes | None:
    start = buffer.find(b"\xff\xd8")
    if start < 0:
        return None
    end = buffer.find(b"\xff\xd9", start + 2)
    if end < 0:
        return None
    return bytes(buffer[start : end + 2])
