# Changelog

## 0.3.0

Combined Monitoring+ and Astro Dashboard release.

### Added

- Target-name sensor from GoTo/tracking/stacking telemetry when available.
- Active-camera sensor.
- Home Assistant runtime session-duration sensor.
- Tele/Wide live-stacking frame counters, target frame counts and shooting-time sensors when progress notification `15209` is observed.
- Storage-used percentage sensor.
- Mount/body-mode diagnostic sensor.
- Last calibration azimuth/altitude diagnostic sensors when reported by the DWARF.
- Last-seen timestamp.
- Last-stack-image-update timestamp.
- Firmware and configured-IP diagnostic sensors.
- Connectivity, imaging, stacking, tracking, GoTo and autofocus binary sensors.
- Sanitized Home Assistant diagnostics download.
- Useful activity/target/frame metadata on the Live stack preview camera entity.

### Changed

- Expanded status decoding for camera, focus and motion operations.
- Target names are decoded from Astro GoTo/tracking state when the device reports them.
- Live-stacking progress is collected opportunistically during the existing short-lived status WebSocket connection; PenguAstro still does not hold a permanent WebSocket connection.
- Last observed per-camera stacking progress is retained while that camera continues stacking.
- README expanded with Astro dashboard guidance, progress limitations, device-password behavior and diagnostics details.

### Safety / compatibility

- Still read-only: no GoTo, motor, focus, capture, filter or power-control commands are sent.
- Existing GUI configuration, multiple-instance support and IP reconfiguration remain unchanged.
- Existing v0.1.x entity unique IDs are preserved for the original entities.

## 0.1.2

- Added Tele Live and Wide Live RTSP camera entities.
- Added Home Assistant stream support for on-demand RTSP viewing.
- Documented RTSP behavior and port 554.

## 0.1.1

- Fixed Live stack preview camera platform loading.
- Added local Home Assistant brand icon/logo assets.

## 0.1.0

- Initial PenguAstro release.
