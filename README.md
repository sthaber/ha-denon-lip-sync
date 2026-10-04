# ha-denon-lip-sync

A Home Assistant **package** that sets a Denon receiver's audio delay based
on the video coming into it. Each frame rate and HDR type gets its own
delay, which you tune from a dashboard while matching test video plays.

I built this because my TV takes longer to process some video formats than
others (24 Hz most of all), so a single audio delay is always wrong for
something. The receiver's Auto Lip Sync is supposed to handle this, but my
TV reports a delay of 0 ms to it no matter what's playing.

Tested on a Denon AVR-X1700H with an Apple TV on AUX1, into an LG C5.

## What you get

- `sensor.denon_lip_sync_format`: what's coming into the receiver, e.g.
  `24_hdr10`. Attributes: `input`, `resolution`, `frame_rate`, `hdr`,
  `delay` (the receiver's current audio delay in ms), and `error`.
- One delay setting for each combination of 24, 50 and 60 Hz with SDR,
  HDR10 and Dolby Vision, e.g. `input_number.lip_sync_24_hdr10`. Nine in all.
- `input_number.lip_sync_default`: used for anything else, such as HLG.

There's no 25 or 30 Hz row because an Apple TV never sends them: it plays
25 fps video at 50 Hz and 30 fps at 60 Hz. If your source does send 25 or
30 Hz, those use the default, or you can add rows the same way.
- An automation that sends the matching delay to the receiver whenever the
  format changes, you switch back to the watched input, or you edit a delay.
- A dashboard for tuning.

## Requirements

- The built-in [`denonavr`](https://www.home-assistant.io/integrations/denonavr/)
  integration is set up for the receiver.
- The video source is plugged into the receiver, not the TV. The receiver
  can only report video it passes through.
- The receiver's Auto Lip Sync is off, so it doesn't add its own delay on
  top.
- `default_config:` is enabled (loads the `command_line` integration).

## Install

```bash
cd /config
git clone https://github.com/sthaber/ha-denon-lip-sync.git
```

Then add this to `configuration.yaml`:

```yaml
homeassistant:
  packages:
    denon_lip_sync: !include ha-denon-lip-sync/entities.yaml
```

and, to get the tuning dashboard in the sidebar:

```yaml
lovelace:
  mode: storage   # leave the default dashboard storage-managed
  dashboards:
    dashboard-lip-sync:   # YAML-mode dashboards must contain a hyphen
      mode: yaml
      filename: ha-denon-lip-sync/dashboard.yaml
      title: Lip Sync
      icon: mdi:timer-music-outline
      show_in_sidebar: true
      require_admin: false
```

Restart HA.

## Configuration

Two spots, both in the automation's `variables:` in `entities.yaml`:

1. **`watched_input: AUX1`**: the input your source is plugged into, by the
   receiver's internal name (`AUX1`, `MPLAY`, `GAME`, `BD`, `SAT/CBL`, ...),
   not the name you gave it. Select the input and read the `input` attribute
   off `sensor.denon_lip_sync_format` to find it.
2. **`receiver: media_player.denon_avr_x1700h_2`**: your receiver's
   `media_player` entity from the `denonavr` integration. If you also use
   HEOS, there may be two entities for the receiver; use the `denonavr` one.

The script finds the receiver's address in your `denonavr` config entry,
so it needs no setup.

## Tuning

1. Play a test clip in one format. Sync test clips with a flash and a beep
   make this much easier.
2. Open the Lip Sync dashboard. The top card shows the format the receiver
   sees and which delay setting is in use.
3. Adjust that setting until the beep lines up with the flash. Each change
   reaches the receiver within a few seconds.
4. Repeat for each format you watch.

Your values are kept in HA's saved state, not in this repo, so updates to
the package don't touch them. They're included in HA backups.

## How it works

- `denon.py` connects to the receiver's control port, asks for the selected
  input, the incoming video's resolution and frame rate, its HDR type, and
  the current audio delay, and prints them as JSON.
- `sensor.denon_lip_sync_format` is a `command_line` sensor that runs the
  script every 3 s.
- The automation picks the delay setting named after the sensor's state
  (`24_hdr10` reads `input_number.lip_sync_24_hdr10`), falling back to the
  default when there isn't one. If that differs from the receiver's current
  delay, it sends the new value with the `denonavr.get_command` service.

### What the receiver reports

From an X1700H with an Apple TV that matches frame rate and dynamic range:

| Playing | `frame_rate` | `hdr` |
| --- | --- | --- |
| 23.976 fps SDR | 24 | `sdr` |
| 50 fps SDR | 50 | `sdr` |
| 59.94 fps SDR | 60 | `sdr` |
| 24 fps HDR10 | 24 | `hdr10` |
| Apple TV menu (4K Dolby Vision) | 60 | `dolby_vision` |

Frame rates are whole numbers, so 23.976 and 24 share a setting, as do
59.94 and 60. The resolution is whatever the source sends: an Apple TV set
to 4K reports 4K even for 1080p video.

## Known limitations

- **Up to 3 s late.** The receiver never announces video format changes, so
  the script polls. When the source switches formats the screen goes black
  for a moment anyway, which hides most of this.
- **Only one input.** The receiver's delay command changes whichever input
  is selected, so the automation only acts while the watched input is
  selected. Each input keeps its own delay on the receiver.
- **Your remote's changes are kept until the format changes.** If you
  adjust the delay with the receiver's own remote, the automation leaves it
  alone until the next format change or input switch, then sets the tuned
  value again.
- **The receiver allows 0 to 500 ms**, so the settings do too.
- **The receiver may show its delay on screen** when it changes, as it
  does for any audio delay change.

## License

MIT — see [LICENSE](LICENSE).
