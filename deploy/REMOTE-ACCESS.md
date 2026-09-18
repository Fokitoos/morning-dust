# Reaching the dashboard from outside the house

What this document decides: how to use morning-dust from a phone when you're
not on the home Wi-Fi, without handing the family's data to the internet.

## What we're protecting

Be clear about the starting point — today the app has **no authentication of
any kind**. Anyone who can reach port 8000 can read *and modify* everything:
the calendar, to-dos, notes, recipes, and the children's weight logs (which is
health data). It also runs plain HTTP, and CORS is wide open (`*`). None of
that matters on a trusted LAN; all of it matters the moment a public IP
routes to the Pi. Port scanners find fresh home-IP services within hours, so
"nobody knows my IP" is not a plan.

## Recommendation: Tailscale, don't expose anything

Install [Tailscale](https://tailscale.com) (a zero-config WireGuard mesh VPN,
free for personal use) on the Pi and on your phone, signed into the same
account:

```bash
# on the Pi
curl -fsSL https://tailscale.com/install.sh | sh
sudo tailscale up
tailscale ip -4        # note the 100.x.y.z address
```

Then install the Tailscale app on the phone, log in, and open
`http://<100.x.y.z>:8000` (or the MagicDNS name, e.g.
`http://raspberrypi:8000`) from anywhere. That's the whole setup.

Why this fits better than any public exposure:

- **No open ports, no attack surface.** The router forwards nothing. Only
  devices logged into your tailnet can reach the Pi at all, so the app's lack
  of authentication stops being a problem — the network *is* the auth.
- **No domain needed, and immune to your home IP changing.** The 100.x
  address is stable; a dynamic public IP breaks nothing.
- **Zero app changes.** The kiosk keeps using localhost; the LAN keeps
  working; the phone just gains one more route in.
- **Traffic is encrypted end-to-end** (WireGuard), so no certificate
  wrangling for a bare IP.

Adding family members later: Tailscale's free plan covers 3 users — invite
them and their phones join the tailnet. DIY WireGuard on the router is the
self-hosted equivalent if you'd rather not involve Tailscale's coordination
service, at the cost of key management and needing one forwarded UDP port.

## If you ever truly need it public (a URL anyone can open)

Only worth it if someone outside the household, who can't join the tailnet,
needs access. Then do **all** of these, not a subset:

1. **App-level auth first, before any port opens.** Simplest fit for this
   codebase: a shared secret in `.env` (`MORNING_DUST_TOKEN`), FastAPI
   middleware that requires it as an `HttpOnly` session cookie, a tiny PIN
   login page that sets the cookie, and an exemption for requests from
   `127.0.0.1` so the kiosk never sees a login screen. No user accounts — one
   family PIN.
2. **Reverse proxy in front.** Bind uvicorn to `127.0.0.1` and put Caddy on
   the Pi terminating TLS on 443 (forward only 443 at the router, never 8000).
   Caddy adds `basic_auth` (bcrypt) as a second, independent gate and rate
   limiting; add fail2ban on its access log.
3. **TLS on a bare IP** is the weak spot of the no-domain constraint:
   Let's Encrypt does issue short-lived IP-address certificates now, but the
   tooling is young; the pragmatic fallback is Caddy's self-signed cert plus
   accepting the browser warning once per device. A €3/year domain would
   dissolve this whole problem — worth reconsidering if you go public.
4. **Accept the operational tax:** a dynamic home IP breaks your bookmark and
   certificate on every renewal; the Pi becomes a machine you must patch
   promptly (`unattended-upgrades`); and `data/morning-dust.db` needs a real
   backup, because it's now one bug away from an internet-reachable wipe.
   Tighten CORS in `app/main.py` (drop the `*`) at the same time.

The honest comparison: option one is ~15 minutes and removes the threat;
option two is an afternoon plus permanent upkeep. For a family dashboard,
take the VPN.
