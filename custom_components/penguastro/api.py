"""Local network client for a DWARFLAB DWARF 3.

Only read-only endpoints/commands are used by PenguAstro.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import UTC, datetime
import logging
import secrets
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
class DeviceStatus:
    """Read-only snapshot from command 16405."""

    battery: int | None = None
    temperature: int | None = None
    tele_cmos_temperature: int | None = None
    wide_cmos_temperature: int | None = None
    storage_available: int | None = None
    storage_total: int | None = None
    focus_position: int | None = None
    shooting_mode_id: int | None = None
    shooting_mode: str | None = None
    tele_stacking_state: int = 0
    wide_stacking_state: int = 0
    tele_stacking: str = "idle"
    wide_stacking: str = "idle"
    activity: str = "Idle"


@dataclass(slots=True)
class PenguAstroData:
    """Coordinator payload."""

    status: DeviceStatus
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
        if "DWARF3" not in name.upper().replace(" ", ""):
            raise PenguAstroProtocolError("The device does not identify as DWARF 3")

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
                    fw_data = fw_payload.get("data", {}) if isinstance(fw_payload, dict) else {}
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
        """Open a short-lived WebSocket, read cmd 16405, and immediately close it."""
        host = _url_host(self.host)
        client_id = f"ha_{secrets.token_hex(5)}"
        packet = _build_state_request(client_id)

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
                            if (
                                envelope.get("cmd") == _CMD_GET_DEVICE_STATE_INFO
                                and envelope.get("type") in _MSG_RESPONSE_TYPES
                                and isinstance(envelope.get("data"), bytes)
                            ):
                                return _parse_device_status(envelope["data"])
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

                # Some firmware may serve a single image body without a useful
                # content type. Try one final extraction before giving up.
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
    # WsPacket: major=1, minor=20, device_id=1, module=14, cmd=16405,
    # type=REQUEST(0), empty ReqGetDeviceStateInfo payload, client_id.
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


def _is_active(state: int) -> bool:
    return state in (1, 2)


def _camera_details(camera_data: bytes | None) -> dict[str, Any]:
    if camera_data is None:
        return {"cmos": None, "states": {}, "stacking": 0}
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
    for field_no, name in names.items():
        raw = _last_bytes(exclusive, field_no)
        if raw is not None:
            states[name] = _operation_state(_decode_fields(raw))

    stacking = states.get("stacking", 0)
    return {"cmos": cmos, "states": states, "stacking": stacking}


def _exclusive_operation(
    payload: bytes | None, mapping: dict[int, str]
) -> tuple[str | None, int | None]:
    if payload is None:
        return None, None
    outer = _decode_fields(payload)
    exclusive = _nested(outer, 1)
    for field_no, name in mapping.items():
        raw = _last_bytes(exclusive, field_no)
        if raw is not None:
            state = _operation_state(_decode_fields(raw))
            if _is_active(state):
                return name, state
    return None, None


def _derive_activity(
    tele: dict[str, Any],
    wide: dict[str, Any],
    focus_data: bytes | None,
    motion_data: bytes | None,
) -> str:
    tele_stack = int(tele["stacking"])
    wide_stack = int(wide["stacking"])
    if _is_active(tele_stack) and _is_active(wide_stack):
        return "Live stacking (Tele + Wide)"
    if _is_active(tele_stack):
        return "Live stacking (Tele)"
    if _is_active(wide_stack):
        return "Live stacking (Wide)"

    for camera_name, camera in (("Tele", tele), ("Wide", wide)):
        for key, label in (
            ("recording", "Recording video"),
            ("timelapse", "Timelapse"),
            ("photo", "Taking photo"),
            ("burst", "Burst capture"),
            ("panorama", "Panorama"),
            ("calibration_frame", "Calibration frame"),
            ("sentry", "Sentry"),
        ):
            state = camera["states"].get(key)
            if state is not None and _is_active(state):
                return f"{label} ({camera_name})"

    focus_name, _ = _exclusive_operation(
        focus_data,
        {1: "Astro autofocus", 2: "Autofocus", 3: "Fast autofocus", 4: "Area autofocus"},
    )
    if focus_name:
        return focus_name

    motion_name, _ = _exclusive_operation(
        motion_data,
        {
            1: "Astro calibration",
            2: "GoTo",
            3: "Astro tracking",
            4: "Tracking",
            5: "One-click GoTo",
            6: "EQ solving",
            7: "Sentry motion",
            8: "Sky target finder",
        },
    )
    if motion_name:
        return motion_name

    return "Idle"


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

    focus_position: int | None = None
    if focus_raw is not None:
        focus_fields = _decode_fields(focus_raw)
        position = _nested(focus_fields, 2)
        focus_position = _last_varint(position, 1)

    battery = temperature = storage_available = storage_total = None
    if device_raw is not None:
        device = _decode_fields(device_raw)
        storage = _nested(device, 4)
        temp = _nested(device, 7)
        battery_info = _nested(device, 9)
        storage_available = _last_varint(storage, 1)
        storage_total = _last_varint(storage, 2)
        temperature = _as_int32(_last_varint(temp, 2))
        battery = _last_varint(battery_info, 1)

    tele_stacking_state = int(tele["stacking"])
    wide_stacking_state = int(wide["stacking"])

    return DeviceStatus(
        battery=battery,
        temperature=temperature,
        tele_cmos_temperature=tele["cmos"],
        wide_cmos_temperature=wide["cmos"],
        storage_available=storage_available,
        storage_total=storage_total,
        focus_position=focus_position,
        shooting_mode_id=shooting_mode_id,
        shooting_mode=SHOOTING_MODES.get(shooting_mode_id, str(shooting_mode_id))
        if shooting_mode_id is not None
        else None,
        tele_stacking_state=tele_stacking_state,
        wide_stacking_state=wide_stacking_state,
        tele_stacking=_state_label(tele_stacking_state),
        wide_stacking=_state_label(wide_stacking_state),
        activity=_derive_activity(tele, wide, focus_raw, motion_raw),
    )


def _extract_jpeg(buffer: bytes | bytearray) -> bytes | None:
    start = buffer.find(b"\xff\xd8")
    if start < 0:
        return None
    end = buffer.find(b"\xff\xd9", start + 2)
    if end < 0:
        return None
    return bytes(buffer[start : end + 2])
