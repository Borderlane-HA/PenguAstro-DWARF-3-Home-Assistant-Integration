# PenguAstro – DWARF 3 Home Assistant Integration

PenguAstro is a local, read-only Home Assistant integration for the **DWARFLAB DWARF 3 Smart Telescope**.

It brings telescope status, battery and temperature monitoring, Astro session information, stacking progress when available, normal Tele/Wide live streams, and a progressively updated live-stack preview into Home Assistant.

Repository: https://github.com/Borderlane-HA/PenguAstro-DWARF-3-Home-Assistant-Integration

> PenguAstro is an independent community project. It is not affiliated with, authorized by, or endorsed by DWARFLAB.

> [!IMPORTANT]
> **DWARFLAB app and PenguAstro access:** When the official DWARFLAB app has an active connection to the DWARF 3, Home Assistant/PenguAstro may temporarily be unable to read the telescope. You can open and use the DWARFLAB app at any time; PenguAstro simply misses that poll and resumes automatically on a later update after the app releases the connection. PenguAstro does not keep a permanent control connection open.
>
> PenguAstro polls by default every **60 seconds**. The interval can be changed later in **Settings → Devices & services → PenguAstro → Configure** (30–3600 seconds).

## Highlights in v0.3.1

v0.3.1 keeps the v0.3 monitoring and Astro Dashboard feature set and adds improved documentation, screenshots, clearer app-coexistence guidance, and a ready-to-copy mobile notification example.

- GUI setup using the local DWARF 3 IP address
- IP address can be changed later with Home Assistant **Reconfigure**
- Multiple DWARF 3 telescopes can be added as separate integration instances
- Default refresh interval: **60 seconds**
- Configurable refresh interval from **30 to 3600 seconds**
- Short-lived WebSocket status reads instead of a permanently connected control client
- No motor, GoTo, focus, capture-start/stop or power-control commands
- Battery and temperature monitoring
- Current shooting mode and best-effort current activity
- Active camera where it can be determined from the device state
- Target name when reported by GoTo, tracking or live-stacking telemetry
- GoTo, tracking, autofocus, stacking and imaging binary sensors
- Local Home Assistant session timer while the telescope is active
- Tele and Wide live-stacking states
- Tele/Wide stacking frame counters and target frame count when the DWARF pushes progress during the short status request
- Tele/Wide stacking shooting time when provided by the DWARF notification
- Free/total/used storage information
- Focus position
- Mount/body mode and last calibration Az/Alt values when available
- Last successful status update timestamp
- Last live-stack image update timestamp
- Firmware and configured IP as diagnostic entities
- Cached live-stack preview from `:8092/mainstream`
- On-demand **Tele Live** RTSP camera
- On-demand **Wide Live** RTSP camera
- Sanitized Home Assistant diagnostics download
- English and German UI translations
- Local PenguAstro icon/logo assets for the Home Assistant UI

## Screenshots

The screenshots use absolute GitHub raw URLs so they are also visible when HACS renders this README.

### Device overview

![PenguAstro device overview](https://raw.githubusercontent.com/Borderlane-HA/PenguAstro-DWARF-3-Home-Assistant-Integration/main/images/penguastro-device-overview.png)

### Diagnostics

![PenguAstro diagnostics](https://raw.githubusercontent.com/Borderlane-HA/PenguAstro-DWARF-3-Home-Assistant-Integration/main/images/penguastro-diagnostics.png)

### Integration options

![PenguAstro update interval options](https://raw.githubusercontent.com/Borderlane-HA/PenguAstro-DWARF-3-Home-Assistant-Integration/main/images/penguastro-options.png)

## Entities

Each configured DWARF 3 creates one Home Assistant device.

### Main sensors

| Entity | Purpose |
|---|---|
| Status | Best-effort current activity such as Idle, Live stacking, Recording video, GoTo, Tracking or Autofocus |
| Battery | Battery level in percent |
| Shooting mode | Normal, DSO, Sun/Moon, Milky Way, Star Trail, Auto Tracking, Panorama, Sun, Moon or Planet |
| Target | Target name when the telescope reports one |
| Active camera | Tele, Wide or Tele + Wide when derivable from the active task |
| Session duration | Home Assistant runtime timer for the current active telescope session |
| Tele stacking | Tele live-stacking state |
| Wide stacking | Wide live-stacking state |
| Tele stack frames | Current Tele frame counter when a live progress notification is observed |
| Tele target frames | Configured Tele target frame count when reported |
| Tele stacking time | Tele shooting time when reported |
| Wide stack frames | Current Wide frame counter when a live progress notification is observed |
| Wide target frames | Configured Wide target frame count when reported |
| Wide stacking time | Wide shooting time when reported |
| Device temperature | Telescope temperature |

### Binary sensors

| Entity | Purpose |
|---|---|
| Connected | Last PenguAstro status poll succeeded |
| Imaging | Photo/video/timelapse/panorama/live-stacking activity is active |
| Stacking | Tele or Wide live stacking is active |
| Tracking | Astro or normal tracking is active |
| GoTo | A GoTo operation is active |
| Autofocus | An autofocus operation is active |

These binary sensors are especially useful for Home Assistant automations and conditional dashboard cards.

### Diagnostic sensors

PenguAstro also exposes:

- Tele CMOS temperature
- Wide CMOS temperature
- Storage available
- Storage total
- Storage used in percent
- Focus position
- Mount/body mode (`EQ`, `Alt-Az`, or unknown when not reported)
- Last calibration azimuth and altitude when available
- Last successful status read
- Last live-stack image update
- DWARF firmware version
- Configured DWARF IP address

## Camera entities

PenguAstro creates three camera entities.

### Live stack preview

`camera.*_live_stack_preview`

While live stacking is active, PenguAstro tries to fetch one current JPEG from:

```text
http://<DWARF-IP>:8092/mainstream
```

The image is fetched only once per configured PenguAstro update interval. With the default configuration this means **one new preview approximately every 60 seconds**.

The last successfully received image stays cached in Home Assistant after stacking stops. This makes it possible to watch a nebula or other target gradually improve without Home Assistant holding the DWARF stack stream permanently open.

The camera entity also exposes useful attributes where available, including activity, target, active stack camera and frame counters.

DWARFLAB documents the `/mainstream` endpoint for Astro live stacking, primarily for the Tele Astro stack. Availability during other stacking modes can depend on firmware/device behavior.

### Tele Live

```text
rtsp://<DWARF-IP>/ch0/stream0
```

### Wide Live

```text
rtsp://<DWARF-IP>/ch1/stream0
```

The RTSP cameras are exposed as native Home Assistant streaming camera entities. PenguAstro does **not** open these RTSP streams as part of its regular 60-second polling.

The DWARF 3 normally provides these RTSP feeds after **LIVE** has been started in the official DWARFLAB app. When an Astro session starts, the normal RTSP live feeds can stop; use **Live stack preview** during Astro stacking.

## About stacking progress

The DWARF 3 pushes live-stacking progress through WebSocket notification `15209`. That message can contain values such as:

- total frame count
- current frame count
- target name
- camera type
- shooting time
- exposure/gain indexes

PenguAstro deliberately does **not** keep a permanent WebSocket connection open just to receive these notifications. Instead, it listens for progress packets that naturally arrive while the short read-only status request is in progress.

Therefore:

- stacking state is reliably available from the normal device-state snapshot,
- frame counters are **best effort**,
- a frame sensor can temporarily be unknown until a progress packet is observed,
- the latest observed progress is retained while that camera continues stacking.

This trade-off keeps PenguAstro much less intrusive toward the official DWARFLAB app.

## Session duration

`Session duration` is maintained by Home Assistant. It starts when PenguAstro observes an active imaging, GoTo, tracking, autofocus or Astro calibration operation and resets when the telescope becomes idle.

It is therefore a useful dashboard timer, but it is **not** claimed to be an authoritative session-start timestamp stored by the telescope. A Home Assistant restart resets this runtime timer.

## Network requirements

The DWARF 3 must be reachable from Home Assistant over the local network.

### Connect the DWARF 3 to Wi-Fi

In the DWARFLAB app, configure **STA mode** or **Auto mode** so the telescope joins your normal Wi-Fi network.

PenguAstro cannot reach a DWARF that is only available through its private hotspot when Home Assistant is on another network.

A DHCP reservation/static lease is strongly recommended.

### Required local ports

| Port | Use |
|---:|---|
| `8082` | HTTP device information and setup validation |
| `8092` | Live-stack preview image |
| `9900` | Read-only WebSocket device-state snapshot |
| `554` | Tele/Wide RTSP live video |

If the DWARF 3 is in an IoT VLAN and Home Assistant is in another VLAN, allow **Home Assistant → DWARF 3** on these ports.

**Never expose these ports directly to the Internet.**

## Important: interaction with the DWARFLAB app

The DWARF 3 effectively gives one client control of the local WebSocket connection at a time. If the official DWARFLAB app is actively connected, PenguAstro may temporarily fail to read status data. This is expected and does **not** prevent you from using the app whenever you want. Home Assistant keeps the last known values and PenguAstro automatically tries again on the next polling cycle.

During development it was also confirmed that a permanently connected third-party WebSocket client can interfere with the official DWARFLAB app. PenguAstro therefore uses this model:

1. connect to port `9900`,
2. send the read-only `TASK_GET_DEVICE_STATE_INFO` (`16405`) request,
3. collect the response and any stacking progress packet that happens to arrive,
4. disconnect immediately,
5. wait until the next update cycle.

With the default 60-second interval, the WebSocket is normally open only very briefly.

A short overlap with the official app can still happen. If the DWARFLAB app behaves strangely while PenguAstro is active, increase the PenguAstro update interval or temporarily disable/reload the integration while doing intensive control work in the official app.

## Device password

PenguAstro does not currently require the DWARF device password. It communicates with an already connected DWARF 3 over its local STA IP.

The local API on firmware tested during development responded without an API authentication challenge. For this reason, the network isolation recommendations above are important even when a DWARF device password has been configured.

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

PenguAstro checks `/deviceInfo` during setup and uses the telescope MAC address as its unique ID. This supports multiple DWARF 3 devices while preventing the same telescope from being added twice.

## Change the IP address later

1. Open **Settings → Devices & services**.
2. Open **PenguAstro**.
3. Open the menu for the affected config entry.
4. Choose **Reconfigure**.
5. Enter the new IP address.

PenguAstro verifies that the new address still belongs to the same DWARF 3 before accepting it.

## Change the update interval

Open the PenguAstro integration entry and choose **Configure**. The default update interval is **60 seconds** and can be changed at any time between **30 and 3600 seconds**.

The same interval is used for status polling and live-stack preview refresh attempts.

## Multiple DWARF 3 telescopes

Run **Add integration → PenguAstro** again for every telescope. Each DWARF receives its own Home Assistant device, entities, cameras, cached live-stack preview and update coordinator.

For multi-device setups, give every DWARF 3 its own DHCP reservation.

## Dashboard idea

A useful Astro dashboard can combine:

- Live stack preview camera
- Status
- Target
- Session duration
- Battery
- Stacking binary sensor
- Tracking binary sensor
- Tele/Wide stack frame counter
- Device temperature
- Last stack image update

The binary sensors also make it easy to display the live-stack card only while stacking is active.

## Example: send the Astro stack image to your phone every 30 minutes

The following Home Assistant automation sends the current cached **Live stack preview** to a mobile device every 30 minutes, but only while PenguAstro reports that stacking is active. GitHub and HACS show a **copy button** on the code block.

Before using it, replace these placeholders with your actual entity/service IDs:

- `binary_sensor.REPLACE_WITH_STACKING_ENTITY`
- `camera.REPLACE_WITH_LIVE_STACK_PREVIEW`
- `notify.mobile_app_REPLACE_WITH_YOUR_PHONE`

```yaml
alias: PenguAstro - Stack image every 30 minutes
description: Send the current DWARF 3 Astro stack preview to a mobile device while stacking is active.
triggers:
  - trigger: time_pattern
    minutes: "/30"
conditions:
  - condition: state
    entity_id: binary_sensor.REPLACE_WITH_STACKING_ENTITY
    state: "on"
actions:
  - action: camera.snapshot
    target:
      entity_id: camera.REPLACE_WITH_LIVE_STACK_PREVIEW
    data:
      filename: /media/penguastro_stack.jpg

  - delay: "00:00:01"

  - action: notify.mobile_app_REPLACE_WITH_YOUR_PHONE
    data:
      title: "PenguAstro"
      message: "DWARF 3 is live stacking – here is the latest preview."
      data:
        image: /media/local/penguastro_stack.jpg
mode: single
```

Home Assistant allows camera snapshots in the default `/media` directory. The Companion App can then attach the resulting `/media/local/penguastro_stack.jpg` image to the notification. If you have multiple DWARF 3 devices, use a different filename for each telescope.

## Diagnostics

Home Assistant's **Download diagnostics** action is supported. PenguAstro diagnostics include integration version, firmware, current decoded status, session state and cached-image state.

The diagnostics output intentionally omits the configured IP address, MAC address, serial number, Wi-Fi password, device password and BLE identifiers.

## Security notes

On firmware used during initial development, `/deviceInfo` can contain sensitive device/Wi-Fi fields. PenguAstro extracts only safe metadata required during setup and never stores or logs the returned Wi-Fi password, device password, serial number or BLE service information.

Recommended setup:

- keep the telescope on a trusted LAN or isolated IoT VLAN,
- allow only Home Assistant / management clients to the required ports,
- never port-forward `554`, `8082`, `8092` or `9900` from the Internet.

## Compatibility

PenguAstro v0.3.1 targets **Home Assistant 2026.6 or newer**.

Initial development and hardware protocol validation were performed against a **DWARF 3 running firmware 1.5.2**. The community SDK used as a protocol reference documents DWARF 3 hardware verification for firmware 1.5.x.

The DWARF protocol is not an official public API and may change with future firmware.

## Current limitations

- PenguAstro is intentionally read-only.
- Stacking frame counters are best effort because the integration does not keep the WebSocket permanently connected.
- Current RA/DEC are not exposed yet. The read-only `16405` snapshot does not provide a reliable current pointing coordinate pair, so PenguAstro does not fabricate one.
- The target name is available only when the DWARF includes it in GoTo/tracking/stacking state.
- The last cached live-stack preview is not necessarily the final saved FITS/JPEG from the DWARF album.
- RTSP availability depends on the DWARF live-view state and firmware behavior.

## How it works

PenguAstro uses only local interfaces:

- HTTP `:8082` for safe device identification
- WebSocket `:9900` for the read-only `TASK_GET_DEVICE_STATE_INFO` (`16405`) snapshot
- opportunistic notification `15209` decoding for live-stacking progress
- HTTP `:8092/mainstream` for the progressively improving live-stack image
- RTSP `:554/ch0/stream0` for Tele Live
- RTSP `:554/ch1/stream0` for Wide Live

The status protocol is protobuf over WebSocket. PenguAstro contains a small purpose-built decoder for the monitoring fields it uses. No Node.js service, external bridge or cloud account is required.

## Credits

The protocol work in PenguAstro was made possible by community reverse engineering and testing, especially:

- [alikh31/dwarflab-sdk](https://github.com/alikh31/dwarflab-sdk) – typed DWARF WebSocket/HTTP protocol reference and DWARF 3 hardware verification
- [acocalypso/dwarfAlp](https://github.com/acocalypso/dwarfAlp) – DWARF/ASCOM Alpaca implementation and additional protocol research
- [DWARFLAB documentation](https://help.dwarflab.com/) – official device/network and stream documentation

## License

MIT License. See [LICENSE](LICENSE).
