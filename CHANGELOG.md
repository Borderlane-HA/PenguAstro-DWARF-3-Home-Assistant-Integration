# Changelog

## 0.1.2

- Added **Tele Live** camera using the DWARF 3 `ch0` RTSP stream.
- Added **Wide Live** camera using the DWARF 3 `ch1` RTSP stream.
- RTSP streams are exposed on demand and are not opened by the normal PenguAstro polling cycle.
- Added Home Assistant `stream` dependency for native RTSP/HLS handling.
- Documented that the official DWARFLAB app must have **LIVE** started before the RTSP feeds are available.
- Documented that normal RTSP video stops during Astro sessions and the Live stack preview should be used instead.
- Added TCP port `554` to the network/firewall documentation.

## 0.1.1

- Fixed the **Live stack preview** camera platform not loading in Home Assistant.
- Added local PenguAstro brand assets (`icon.png` / `logo.png`, including 2x and dark variants) for Home Assistant 2026.3+.
- Added clearer README instructions for locating the live-stack camera and adding it to a dashboard.
- Clarified that the DWARFLAB HTTP stacking stream is primarily intended for the tele-photo Astro stack.

## 0.1.0

- Initial PenguAstro release.
- GUI setup by local DWARF 3 IP address.
- Reconfigure flow for IP address changes.
- Multiple DWARF 3 instances supported and identified by MAC address.
- 60-second default read-only status polling with short-lived WebSocket connections.
- Battery, activity, shooting mode, Tele/Wide stacking state, temperatures, storage and focus sensors.
- Cached live-stack preview from port 8092 while stacking is active, refreshed with the coordinator interval and retained afterwards.
- English and German translations.
- HACS custom-repository metadata and installation documentation.
