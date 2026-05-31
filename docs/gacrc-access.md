# GACRC access from elis

How the **elis** dev box connects to GACRC (UGA's HPC). Primary target is the
**teach** cluster — it's underused, so queues are usually faster than Sapelo2 —
plus **Franklin's** multi-GPU compute nodes. (No access to the "real" Sapelo2.)

## TL;DR — daily use

```bash
gacrc-vpn up        # connect the VPN: MyID password, then Duo (type 'push')
ssh teach           # key login — NO password, NO Duo
gacrc-vpn status    # check tunnel + teach reachability
gacrc-vpn down      # disconnect
```

The VPN session lasts ~24h, so you'll run `gacrc-vpn up` about once a day.
`gacrc-vpn` lives at `~/bin/gacrc-vpn`.

## Why a VPN is needed

elis is on the private fleet LAN (`10.164.0.0/16`, gw `10.164.100.1`); GACRC
(`128.192.x`) only accepts connections from UGA networks. So elis joins UGA's
full-tunnel VPN (`remote.uga.edu`, AnyConnect, group **"01 Default"**) directly
via `openconnect`.

**Lockout guard:** elis is administered over SSH *from the tower*
(`itacolomi`, `10.164.10.10`). A full-tunnel VPN would send elis's replies up
the tunnel and kill that session. Prevented by a persistent NetworkManager route
pinning the fleet subnet to the LAN (more specific than the VPN's pushed
`0.0.0.0/1`, so it wins):

```bash
# already in the enp1s0 profile (survives reboot); gacrc-vpn re-asserts it
sudo nmcli connection modify enp1s0 +ipv4.routes "10.164.0.0/16 10.164.100.1"
```

## SSH key

A dedicated key `~/.ssh/gacrc_ed25519` is installed in `teach:~/.ssh/authorized_keys`.
On **teach**, public-key auth satisfies the *entire* login — no MyID password and
no Duo (verified 2026-05-29). The `teach` block in `~/.ssh/config` uses the key
with `IdentitiesOnly yes` + connection multiplexing (`ControlMaster`/`ControlPersist 8h`),
so one connection is reused for many `ssh`/`scp`/`rsync`/`sbatch` calls.

## Manual VPN command (what gacrc-vpn wraps)

```bash
sudo openconnect --protocol=anyconnect --background \
  --user=mpk15956 --authgroup="01 Default" remote.uga.edu
```
