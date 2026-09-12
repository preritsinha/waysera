# Waysera — Every journey, together.

Waysera is a live group-navigation app for people heading to the same place.
Start a journey, share a six-character code, and everyone appears on one map as
they travel. No account, no sign-up.

It is built so that **we cannot see your journey**. Positions, names, messages
and destinations are encrypted on your device before they leave it.

---

## What it does

- **One live map for the whole group.** Everyone's position, speed and heading,
  plus how far each person is from you and from the destination.
- **Six-character codes.** Read one out loud, or send a link. Nothing to sign up
  for.
- **Turn-by-turn navigation** with voice guidance, and it reroutes if you come
  off course.
- **Tap-only messages.** "Pulling over", "Need fuel", "Go ahead without me". No
  typing while driving.
- **Journey replay.** Scrub back through a finished journey at up to 10× and see
  what happened, and when.
- **Export.** Take a journey away as JSON, or as GPX for any mapping tool.

Finished journeys stay in a list on your device until you delete them.

---

## How the privacy works

The server is a **relay**, not a database.

```
You  ──encrypted──┐                    ┌──encrypted── Priya
                  ├─→  Waysera relay  ─┤
Sam  ──encrypted──┘   (forwards bytes) └──encrypted── Alex
```

Every journey has a key made on the device that started it. That key travels in
the part of a link after the `#`, which browsers never send to any server. The
relay only ever sees scrambled bytes and has no way to unscramble them. It
stores nothing.

If you join by typing a code instead of opening a link, you have no key yet — so
somebody already in the journey has to look at your name and tap **Allow**. That
tap is deliberate. It is the only thing standing between your group and a
stranger who guessed the code.

### What this does not mean

Waysera cannot see your journey. That is not the same as your location never
leaving your device, and it would be dishonest to claim otherwise:

| Service | What it receives |
| --- | --- |
| Stadia Maps | Requests for map tiles, which reveal the area you are looking at |
| Photon (Komoot) | Every destination you search for, and roughly where you are |
| openstreetmap.de | Your start **and** destination, for every route |

Photon is the sharpest of the three: it learns both where you are and where you
are going. That is the price of search that finds the cafe down the road instead
of a village in Norway. It is a deliberate trade, not an oversight.

We also do not claim: guaranteed security, suitability for emergencies, or
unlimited group size.

---

## Getting the app

### On Android

**There is no download yet.** The app is built and working, but it has not been
released — the version in this repository is a development build that points at
a test server, so it cannot reach anybody else.

When there is a release it will appear here, and installing it will mean
downloading one file and tapping it. Android allows that without any store or
account; your phone will ask you to confirm first, which is normal.

### On iPhone

There is no iOS app. Apple does not allow apps to be installed outside the App
Store, so this needs a different route and has not been built yet.

### In a browser, today

Waysera runs in any modern mobile browser with no install at all — that is where
it started. The one thing a browser cannot do is keep sharing your position once
you switch away from the tab or your screen locks, which is exactly when a group
most wants to see you moving. That limitation is the reason the Android app
exists.

---

## Using it

**Starting a journey.** Search for where you are going, enter your name the
first time, and tap *Create journey*. You land straight on the map with a code
to share.

**Joining one.** Open the link somebody sent you, or tap *Join* and type the
six-character code. If you typed a code, wait a moment — somebody already in the
journey has to let you in.

**On the way.** Everybody shows on the map with how far they still have to go.
Tap *Start navigation* for turn-by-turn directions. The quick-message buttons
send a short note without typing.

**Arriving.** Once everybody has reached the destination the journey finishes on
its own.

**Afterwards.** Finished journeys stay on the home screen. Open one to replay it
or export it.

---

## What it will not do

- **It will not track anyone quietly.** People appear on the map only while they
  have a journey open, and only to the people in it.
- **On the web, it stops when you look away.** Browsers suspend location for
  hidden tabs. The Android app keeps going, and shows a permanent notification
  while it does — Android requires that, and it is the honest signal that
  something is using your location.
- **Nothing survives losing your phone.** There is no copy anywhere else. That
  is the trade the privacy model makes, so export a journey if you want to keep
  it.
- **A journey ends when everyone arrives, or when the last person leaves.**

---

## Questions

**Do I need an account?** No. There is nothing to sign up for and no password.

**Can Waysera see where I am?** No. The relay forwards scrambled bytes it has no
key for. Map and search providers do see some of it — the table above says
exactly what.

**What if I lose signal?** The app reconnects on its own. Your group sees you go
stale, then offline, and you reappear where you are when signal returns.

**Can someone guess my code?** They would have to guess six characters and then
be let in by somebody already there. Refusing a request tells them nothing.

**Is it free?** Yes, and there is nothing to pay for. It is open source under
the MIT licence.

---

## For developers

Architecture, the relay protocol, build instructions and the test suites are in
[DEVELOPING.md](DEVELOPING.md).

---

## License

MIT. See [LICENSE](LICENSE).
