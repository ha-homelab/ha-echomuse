# Device access and administrator credentials

This guide describes the installed emOS **0.10**, EchoMuse device firmware
**2.18.0**, and controller **2.26.0**. Both converted Echo Dot 2 units use this
stack. UI labels and access behavior were checked against pinned upstream
commit `e119433c0845dfe80f4b1ec44c9e8e8028adbb07`.

## What runs where

- **emOS runs on each Dot.** It is a small Linux userspace built around that
  device's original kernel. It replaces the running Amazon/Android userspace;
  selected libraries and hardware firmware still come from the original
  read-only system partition. It is not a general-purpose desktop distribution.
- **EchoMuse device firmware runs on emOS.** It handles microphones, the
  speaker, buttons, LEDs, wake detection and the controller connection.
- **EchoMuse Controller runs on the separate Linux server.** It provides the
  dashboard, configuration, device console and the ESPHome interface to HA.
- **Home Assistant and the speech services run separately.** They handle home
  commands, conversation and speech processing. Changing the Russian voice,
  conversation model, room assignments or light aliases does not require
  reflashing the Dot.

For the installed versions and migration evidence, see the
[current status](../README.md#current-status) and
[deployment record](deployment-record.md).

## Sign in to the controller

1. Open `http://<controller-address>:8768` on the trusted local network, or use
   the deployment's configured HTTPS endpoint or SSH tunnel. This is the
   **controller's address**, not the Dot's address or HA's address.
2. Sign in using the controller administrator account created during its
   first-run setup. There is no shared factory username/password to try.
3. Select an approved, connected Dot and open its **Console** tab. This tab
   contains the shell terminal; in controller 2.26.0 the tab label is Console,
   not Shell. A read-only account cannot open the device shell.
4. Confirm the selected device before entering commands. Close the Console
   tab when finished.

### Where the credentials come from

Our deployment bootstrap saved a local `credentials.private.json` receipt
inside the ignored `private/` deployment directory. It contains `url`,
`username` and `password`. The operator receives the exact local path privately;
neither that file nor actual login values belong in this public repository.
Open the receipt locally, or retrieve the credentials from the operator's
password manager if they have been moved there. Keep the file readable only
by its owner (`0600`). A clone of the public repository will not contain it.

These are **EchoMuse dashboard credentials**. They are separate from the HA
account, Wi-Fi password, per-device TLS token and optional USB console password.
The authenticated administrator session authorizes the network console; there
is no additional Linux username/password prompt for that console.

For a new installation, the one-time bootstrap token in the controller's
private startup logs is used to create the first administrator. It is not the
password for an already initialized controller. The controller stores password
hashes, not a recoverable copy of the original password.

An authenticated user can change their password at **Settings → Account**.
Update the private receipt/password manager after a change. If all valid
credentials are lost, preserve the controller data and arrange a version-specific
account recovery; deleting its database to restart setup would also discard
device approval, configuration and other state. No account-reset procedure is
claimed as tested by this deployment.

## What the network console can do

The terminal executes **on the selected Dot with root privileges**. The browser
connects to the controller; the Dot opens an authenticated shell connection
back to the controller on demand. The installed deployment requires TLS for
this device link. It does not require a public SSH or Telnet listener on the Dot.

Useful initial read-only commands are:

```sh
id
cat /etc/os-release
uname -a
uptime
ps
df -h
```

Use the dashboard's **Status** and **Logs** tabs for routine diagnosis. Root
shell access also permits inspecting files, processes, network interfaces,
audio controls and kernel diagnostics, or making device-level changes.
Command availability depends on the installed BusyBox/system utilities.
Additional binaries must match the Dot's architecture and runtime; these two
units use the ARM32 Fire OS 6 kernel, so ordinary x86 server binaries will not run.

Prefer dashboard configuration for supported audio, wake-word and network
settings: a manual file edit may be overwritten by the controller or an update.
Root access can also overwrite boot partitions or disconnect the device.
Firmware writes and recovery therefore follow the [migration runbook](migration.md),
not an improvised shell command. Keep shell output containing credentials,
device identifiers or transcripts out of public issues and commits.

## USB console and recovery

A powered Dot on Wi-Fi needs **no USB connection to Synology** for normal use
or the network Console. USB is useful when the device cannot reach its
controller or needs boot-time diagnosis/recovery.

Connect the intended Dot with a USB data cable. emOS exposes a serial console
rather than Android ADB. In this deployment the USB identity was `1949:2007`,
manufacturer EchoMuse, product emOS. Match the physical unit and its private
identity before opening a port; a USB device node can change after a reboot.

Use the pinned [emconsole.py helper](https://github.com/wilbowes/EchoMuse/blob/e119433c0845dfe80f4b1ec44c9e8e8028adbb07/emos/tools/emconsole.py)
or a correctly configured serial terminal. The helper performs the raw-mode,
echo-off and newline handshake required for a working shell. See
[USB boot and console verification](migration.md#7-boot-emos-and-enroll-the-pilot)
before interpreting an unresponsive terminal as a failed boot.

The USB console gives root access. An optional password can be set fleet-wide
under **Settings → Config → Advanced → USB console**; it is separate from the
dashboard password. Without that setting the upstream default is an
unauthenticated USB root shell. This guide does not assert that a USB password
is currently configured on either unit. Boot diagnostics remain readable even
when the shell is password-protected.

## SSH, Telnet and ADB limits

- **SSH:** no SSH service was installed or enabled in this rollout. Upstream
  describes Dropbear as an optional per-device opt-in, off by default. This is
  not a verified installation recipe or dashboard toggle in our pinned setup;
  `ssh root@<dot-address>` is not the documented access method. Enabling SSH
  would be a separate change requiring its own authentication and network checks.
- **Telnet and a web server on the Dot:** neither is part of the installed
  access path. The web interface lives on the controller.
- **ADB:** emOS has no ADB daemon. Former EchoLocal/Fire OS commands such as
  `adb connect` or `adb shell` do not work while emOS is booted. Recovery mode
  is a separate environment covered by the migration procedure.

## Validation and sources

For this documentation update, the saved administrator credentials were tested
against the running controller: login succeeded with the `admin` role, and the
temporary session was explicitly logged out. The receipt was verified as
owner-only and ignored by Git. No password was changed, no SSH service was
enabled and neither Dot was reflashed. Console behavior above is based on the
pinned implementation; this update did not open a new shell on either Dot.

- [Pinned emOS documentation](https://github.com/wilbowes/EchoMuse/blob/e119433c0845dfe80f4b1ec44c9e8e8028adbb07/emos/README.md)
- [Device/controller shell protocol](https://github.com/wilbowes/EchoMuse/blob/e119433c0845dfe80f4b1ec44c9e8e8028adbb07/docs/device-controller-interface.md)
- [Dashboard implementation and account settings](https://github.com/wilbowes/EchoMuse/blob/e119433c0845dfe80f4b1ec44c9e8e8028adbb07/controller/static/dashboard.jsx)
- [Controller authentication](https://github.com/wilbowes/EchoMuse/blob/e119433c0845dfe80f4b1ec44c9e8e8028adbb07/controller/em_auth.py)
