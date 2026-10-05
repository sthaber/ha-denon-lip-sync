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
- An automation that keeps the selected input's delay where it should be:
  the matching setting on the input your source is plugged into, and 0 ms
  on every other input.
- `input_boolean.lip_sync_enabled`: turns the automation off, so you can
  set a delay by hand with the receiver's remote for content that's out of
  sync at the source. Turning it back on restores the tuned delay.
- A dashboard for tuning, with the on/off switch at the top.

## Requirements

- The built-in [`denonavr`](https://www.home-assistant.io/integrations/denonavr/)
  integration is set up for the receiver. The script reads the receiver's
  address from it.
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

Restart HA, then turn on **Automatic lip sync** at the top of the
dashboard. It starts off on a new install.

## Configuration

One spot in `entities.yaml`: **`AUX1`** at the end of the sensor's
`command:`. That's the input your source is plugged into, by the
receiver's internal name (`AUX1`, `MPLAY`, `GAME`, `BD`, `SAT/CBL`, ...),
not the name you gave it. Select the input and read the `input` attribute
off `sensor.denon_lip_sync_format` to find it.

The script finds the receiver's address in your `denonavr` config entry,
so it needs no other setup.

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

- `denon.py AUX1` connects to the receiver's control port, asks for the
  selected input, the incoming video's resolution and frame rate, its HDR
  type, and the current audio delay, and prints them as JSON.
- `sensor.denon_lip_sync_format` is a `command_line` sensor that runs it
  every 3 s.
- The automation works out what the selected input's delay should be. On
  the watched input, that's the setting named after the sensor's state
  (`24_hdr10` reads `input_number.lip_sync_24_hdr10`), or the default if
  there isn't one. On any other input, it's 0. If the receiver's delay
  differs, the automation runs `denon.py set <input> <delay>`.
- The receiver has no way to set the delay for a particular input; its
  command changes whichever input is selected. So `denon.py set` asks which
  input is selected and sends the delay over the same connection a moment
  later, and does nothing if the input has changed. The next poll sees the
  new input and the automation decides again.
- The receiver silently ignores delay changes while no video is coming in.
  `denon.py set` only counts a change as made when the receiver repeats
  the exact value back, and the automation re-checks every 10 s, so a
  change that didn't take is retried.

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
- **Only one input is tuned.** Every other input is held at 0 ms. If a
  wrong value ever lands on another input, for example because you switched
  inputs at the exact moment a delay was sent, it's put back to 0 within a
  few seconds.
- **Delay changes from the receiver's remote don't stick** while automatic
  lip sync is on; the automation puts the tuned value back within a few
  seconds. Turn it off to set a delay by hand.
- **Nothing changes while there's no video.** The receiver ignores delay
  changes on any input with no video coming in, such as when the source is
  asleep, so the automation waits. It checks every 10 s and applies the
  delay once video arrives.
- **The receiver allows 0 to 500 ms**, so the settings do too.
- **The receiver may show its delay on screen** when it changes, as it
  does for any audio delay change.

## License

MIT — see [LICENSE](LICENSE).
