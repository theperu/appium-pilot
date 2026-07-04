---
name: appium-pilot
description: Drive a native mobile app (iOS Simulator / Android Emulator) from the terminal via Appium — snapshot the screen to get element refs, then tap/type/swipe/scroll by ref. Use when the user needs to automate, test, inspect, or interact with a mobile app: navigating screens, filling forms, tapping buttons, taking device screenshots, or extracting on-screen content.
---

# appium-pilot

A stateful, session-based CLI for driving a native mobile app. One verb per
invocation; session state persists between calls (the Appium server holds the
live session). Output is tuned for you to read.

## The core loop

1. `appium-pilot open ...` once to start a session.
2. `appium-pilot snapshot` to see the screen as filtered XML with `ref="eN"` ids.
3. Act on a ref: `appium-pilot tap e7`, `appium-pilot type e3 "hello"`, etc.
4. **Re-`snapshot` after anything that changes the screen** — refs are only
   valid until the next snapshot. Acting on a stale ref fails with exit code 2
   and the message "run snapshot again".

## Starting a session

```bash
# Installed Android app (auto-picks a booted emulator, else boots one)
appium-pilot open --platform android --app-package com.example.app

# iOS Simulator app bundle, or an installed app by bundle id
appium-pilot open --platform ios --app /path/to/MyApp.app
appium-pilot open --platform ios --bundle-id com.apple.Preferences

# Target a specific device; add capabilities
appium-pilot open --platform ios --bundle-id com.x --device "iPhone 16"
appium-pilot open --platform android --app-package com.x --cap appium:noReset=true
```

Platform is inferred from `--bundle-id` (ios), `--app-package` (android), or the
app file extension; otherwise pass `--platform`.

## Inspecting

```bash
appium-pilot snapshot          # filtered XML + refs (use this, not --raw, by default)
appium-pilot snapshot --raw    # full unfiltered page source (when filtered hides something)
appium-pilot source            # raw page source, no refs
appium-pilot screenshot        # save PNG, prints path — then Read the file to view it
appium-pilot screenshot e7     # screenshot just one element

appium-pilot get e3            # a ref's current state, e.g. text="hi" enabled=true
appium-pilot get e3 bounds     # read one raw attribute (bounds, focused, ...)
```

Read an element by its attributes in the snapshot: `text`/`desc`/`id` on
Android, `name`/`label`/`value` on iOS. Use `get <ref>` to re-check one
element's live state (e.g. confirm a field's text after `type`) without paying
for a full re-`snapshot`.

## Recording

```bash
appium-pilot video-start                 # start screen recording (--quality low|medium|high, iOS)
# ... drive the app ...
appium-pilot video-stop                  # stop, saves an .mp4, prints its path
appium-pilot video-stop -o run.mp4       # custom output path
```

Screenshots and videos are written under `./appium-pilot/` in the current
directory (set `APPIUM_PILOT_OUTPUT` to change the root). Session state, separately,
lives in `~/.appium-pilot/`.

## Acting (all use refs from the latest snapshot)

```bash
appium-pilot tap e7                             # tap by ref (preferred)
appium-pilot tap --text "Login"                 # tap by visible text (element the filter missed)
appium-pilot tap --at 200,640                   # tap raw coordinates (last resort)
appium-pilot tap e7 --long                      # long-press (--duration secs, default 1.0)
appium-pilot tap e7 --double                    # double-tap
appium-pilot type e3 "user@example.com"        # types into the field
appium-pilot type e3 "pw" --clear --submit     # clear first, press enter/return after
appium-pilot clear e3
appium-pilot hide-keyboard                      # iOS: dismisses via Done/Return

appium-pilot swipe up                           # also: down | left | right; --amount 0.5
appium-pilot swipe coords 200 800 200 200       # explicit x1 y1 x2 y2
appium-pilot scroll e20                          # scroll a ref into view
appium-pilot scroll --to "Privacy"              # scroll until text appears (refreshes refs)

appium-pilot press back                          # android: back | home | enter | <keycode>
appium-pilot press home                          # ios: home | enter only (no system back)
appium-pilot orientation landscape               # or: portrait; omit to read current
```

### System alerts / permission dialogs

Popups like "Allow notifications?" aren't in the app's view hierarchy, so refs
don't reach them — use `alert`:

```bash
appium-pilot alert            # print the alert's text (exit 2 if none shown)
appium-pilot alert accept     # tap its accept/OK button
appium-pilot alert dismiss    # tap its cancel/deny button
```

To skip permission prompts entirely, launch with `open --auto-accept-alerts`
(sets `autoGrantPermissions` on Android / `autoAcceptAlerts` on iOS).

## Waiting (for async UI)

```bash
appium-pilot wait e7                  # until the ref's element is present
appium-pilot wait --text "Welcome"   # until text appears
appium-pilot wait --gone e7          # until it disappears
appium-pilot wait e7 --timeout 20
```

## App lifecycle

```bash
appium-pilot launch | terminate | reset      # acts on the session's app
appium-pilot background 5                     # background for N seconds (-1 = indefinitely)
appium-pilot install /path/to/app            # install an artifact
appium-pilot remove com.example.app          # uninstall
```

## Sessions & environment

```bash
appium-pilot -s=checkout open ...    # named session (default: "default"); -s anywhere before the verb
appium-pilot list                     # active sessions
appium-pilot devices                  # available simulators/emulators
appium-pilot close                    # end one session
appium-pilot close-all                # end all sessions
appium-pilot kill-all                 # stop the Appium server + drop all session state
appium-pilot doctor                   # diagnose setup (never installs anything)
```

## Conventions

- Add `--json` to any command for structured output.
- Success → stdout + exit 0. Errors → stderr + nonzero exit. A **stale/unknown
  ref → exit code 2**: re-`snapshot` and retry with the new refs.
- If `open` is slow on iOS the first time, that's WebDriverAgent building — wait.
- Run `appium-pilot doctor` first if anything fails; it lists exactly what's missing.

## Tips

- Prefer acting by ref over coordinates — refs survive layout shifts; coordinates
  don't.
- `scroll --to "<text>"` is the reliable way to reach off-screen content; it
  refreshes the ref map when it lands.
- iOS keyboards can cover elements; use `type --submit` or `hide-keyboard`
  between fields.
