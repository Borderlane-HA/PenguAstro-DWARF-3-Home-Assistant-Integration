# 🔭 PenguAstro – DWARF 3 Home Assistant Integration

**PenguAstro** is an unofficial Home Assistant integration for the **DWARFLAB DWARF 3 Smart Telescope**. It brings useful telescope status information and a periodically refreshed **live-stack preview** into Home Assistant without trying to replace the official DWARFLAB app.

> PenguAstro is an independent community project and is not affiliated with, authorized by, or endorsed by DWARFLAB.

## Features

PenguAstro v0.1.0 is intentionally focused on **monitoring**.

- GUI setup – no YAML required
- Local IP address entered during setup
- IP address can be changed later with **Reconfigure**
- Multiple DWARF 3 devices can be added as separate integration instances
- Default refresh interval: **60 seconds**
- Refresh interval can be changed from **30 to 3600 seconds**
- The stack-image endpoint is queried only while Tele or Wide stacking is active; the last successful preview remains available afterwards
- Short-lived WebSocket status connection instead of a permanently connected control client
- Cached live-stack preview from the DWARF 3 local stack-image endpoint
- English and German UI translations

### Entities

Each configured DWARF 3 creates one Home Assistant device with these entities:

| Entity | Purpose |
|---|---|
| Status | Best-effort current activity such as Idle, live stacking, recording, GoTo, tracking or autofocus |
| Battery | Battery level in percent |
| Shooting mode | Normal, DSO, Sun/Moon, Milky Way, Star Trail, Auto Tracking, Panorama, Sun, Moon or Planet |
| Tele stacking | Tele live-stacking state |
| Wide stacking | Wide live-stacking state |
| Device temperature | Telescope temperature |
| Tele CMOS temperature | Tele camera sensor temperature |
| Wide CMOS temperature | Wide camera sensor temperature |
| Storage available | Free storage reported by the telescope |
| Storage total | Total storage reported by the telescope |
| Focus position | Current focus motor position |
| Live stack preview | Cached JPEG preview of the currently building astro stack |

The live-stack camera does **not** open a permanent video stream in Home Assistant. While Tele or Wide stacking is active, PenguAstro tries to fetch one current JPEG from `http://<DWARF-IP>:8092/mainstream` on every update cycle and keeps the last successful image in memory. When stacking stops, the last successful preview remains visible. This gives a dashboard view that gradually improves as the telescope adds more frames.

## Network requirements

The DWARF 3 must be reachable by Home Assistant over the local network.

### 1. Connect the DWARF 3 to your Wi-Fi

In the DWARFLAB app, configure the telescope for **STA mode** or **Auto mode** so it joins your normal Wi-Fi network. PenguAstro cannot use the DWARF's private hotspot if Home Assistant is on another network.

A DHCP reservation / static lease is strongly recommended so the telescope keeps a predictable address.

### 2. Allow Home Assistant to reach the DWARF 3

PenguAstro uses these local TCP ports:

| Port | Use |
|---:|---|
| `8082` | HTTP device information / setup validation |
| `8092` | Live-stack preview image |
| `9900` | Read-only WebSocket status snapshot |

If the DWARF 3 is in an IoT VLAN and Home Assistant is in another VLAN, add firewall rules that allow **Home Assistant → DWARF 3** on these ports.

**Do not expose these ports to the Internet.** They are intended for local-network access only.

## Important: interaction with the official DWARFLAB app

The DWARF 3 does not always behave well when multiple WebSocket clients are connected at the same time. During development, a permanently connected third-party WebSocket client prevented the official DWARFLAB app from connecting normally.

PenguAstro therefore deliberately does **not** keep port `9900` open:

1. connect to the DWARF 3,
2. send the read-only device-state request,
3. receive the response,
4. disconnect immediately,
5. wait until the next update cycle.

With the default 60-second interval, the WebSocket is normally open only very briefly. Even so, a short overlap with the official app is still possible. If the DWARFLAB app behaves strangely while PenguAstro is enabled, increase the PenguAstro update interval or temporarily disable/reload the integration while actively controlling the telescope.

PenguAstro v0.1.0 sends **no motor, focus, camera, GoTo, stacking-start/stop or power-control commands**.

## HACS installation

Until PenguAstro is available in the default HACS repository list, add it as a custom repository.

1. Open **HACS** in Home Assistant.
2. Open **Integrations**.
3. Use the three-dot menu and choose **Custom repositories**.
4. Add:

   `https://github.com/Borderlane-HA/PenguAstro-DWARF-3-Home-Assistant-Integration`

5. Select category **Integration**.
6. Search for **PenguAstro** and install it.
7. Restart Home Assistant.
8. Open **Settings → Devices & services → Add integration**.
9. Search for **PenguAstro**.
10. Enter the local IP address of the DWARF 3, for example `10.10.4.104`.

PenguAstro checks `/deviceInfo` during setup and uses the telescope MAC address as its unique ID. This allows multiple DWARF 3 devices to be configured while preventing the same telescope from being added twice.

## Change the IP address later

If DHCP gives the telescope a new address:

1. Open **Settings → Devices & services**.
2. Open **PenguAstro**.
3. Open the menu for the affected config entry.
4. Choose **Reconfigure**.
5. Enter the new IP address.

PenguAstro verifies that the new address still belongs to the same DWARF 3 before accepting the change.

## Change the update interval

Open the PenguAstro integration entry and choose **Configure**. The interval can be set between **30 and 3600 seconds**. The default is **60 seconds**.

The same interval is used for status polling and for attempting to refresh the cached live-stack preview.

## Multiple DWARF 3 telescopes

Simply run **Add integration → PenguAstro** again for each telescope. Each telescope gets its own Home Assistant device, entities, cached preview and update coordinator.

For multi-device setups, assign every DWARF 3 a separate DHCP reservation.

## Security notes

On the firmware used during initial development, the local `/deviceInfo` response can contain sensitive device/Wi-Fi fields. PenguAstro intentionally extracts only the device name and MAC address from that response and never stores or logs the returned Wi-Fi password, device password, serial number or BLE service information.

For that reason, and because the DWARF local APIs are designed for trusted local use:

- keep the telescope on a trusted LAN or isolated IoT VLAN,
- only allow the Home Assistant host / management clients to reach the required ports,
- never port-forward `8082`, `8092` or `9900` from the Internet.

## Compatibility

PenguAstro v0.1.0 targets **Home Assistant 2026.6 or newer**. Initial development and protocol validation were performed against a **DWARF 3 running firmware 1.5.2**. The community SDK used as a protocol reference reports real-hardware verification for DWARF 3 firmware 1.5.x.

The DWARF protocol is not an official public API and may change with future firmware. If a firmware update breaks PenguAstro, please open an issue and include the DWARF firmware version and Home Assistant version.

## How it works

PenguAstro uses the DWARF 3 local interfaces only:

- HTTP `:8082` for safe device identification
- WebSocket `:9900` for the read-only `TASK_GET_DEVICE_STATE_INFO` (`16405`) snapshot
- HTTP `:8092/mainstream` for the progressively improving live-stack image

The status protocol is protobuf over WebSocket. PenguAstro contains a small, purpose-built decoder for the fields needed by the monitoring entities; no Node.js service, external bridge or cloud account is required.

## Credits

The protocol work in PenguAstro was made possible by community reverse engineering and testing, especially:

- [alikh31/dwarflab-sdk](https://github.com/alikh31/dwarflab-sdk) – typed DWARF WebSocket/HTTP protocol reference and DWARF 3 hardware verification
- [acocalypso/dwarfAlp](https://github.com/acocalypso/dwarfAlp) – DWARF/ASCOM Alpaca implementation and additional protocol research
- [DWARFLAB documentation](https://help.dwarflab.com/) – official device/network and stream documentation

## License

MIT License. See [LICENSE](LICENSE).
