# Check catalog

> [中文版](check-catalog.zh-CN.md)

What each row produced by `sweep.py plan` asks you to look at, and what a worrying answer looks like. Menu names differ between OS versions and apps, so describe what you see rather than relying on exact paths.

## Account layer (`A-<account>-...`)

| key | look at | worrying answer |
|---|---|---|
| `sessions` | the account's list of signed-in devices and recent logins | a device, browser or place the person does not recognise |
| `recovery` | recovery email and phone number | an address or number someone else controls |
| `second_factor` | where the second login step goes | codes go to a phone or app the person does not hold alone |
| `forwarding` | mail forwarding addresses, filters, delegates | a rule silently copying or deleting mail |
| `linked_devices` | messaging apps' "linked devices" / web sessions | a session the person never opened |
| `app_access` | third-party apps allowed into the account | an app with mail or file access nobody remembers adding |
| `sharing` | location, calendar, photo, file and family sharing | someone still receiving live location or albums |
| `password_known` | has anyone ever chosen, been told or seen this password | yes, especially the suspected watcher |

## Device layer (`D-<device>-...`)

**Android:** device admin apps; accessibility services; notification access; which apps may install other apps; work profile or organisation management; full app list including system-looking names; VPN profiles and user certificates; the store's built-in malware scan.

**iPhone:** the built-in sharing-and-access review (Safety Check on recent versions); configuration profiles and device management; devices signed into the Apple account; app list; VPN and trusted certificates; signs of a jailbreak such as unexpected package-manager apps.

**Windows / Mac / Linux:** remote-access and screen-sharing software; startup or login items, scheduled tasks, services; browser extensions in every profile; local admin accounts; privacy grants such as screen recording or full disk access; configuration profiles; SSH authorized keys.

A worrying answer is anything with broad powers (read notifications, see the screen, control the device, read all files) that the person cannot name or did not install.

## Tracker layer (`T-...`)

| key | look at | worrying answer |
|---|---|---|
| `unknown_tracker_alert` | the phone's alerts for unknown trackers travelling with you | an alert, especially repeated |
| `physical_look` | bag linings, coat pockets, car (wheel arches, under seats), gifts | a small disc or tag the person did not buy |
| `map_sharing` | live location sharing in map, family and fitness apps | someone still receiving live location |

## Indicator layer (`I-<device>`)

An offline scan of a phone backup or a structured collection against published indicators of known spyware, done with a trusted forensic toolkit. Planned only when the watcher may be state-level. Run it offline, keep the backup private, never contact any address found in the indicators, and read the tool's own statement of what it could not check. A match is a lead to confirm with an expert, not a final answer; no match means only that the loaded indicators were not found in the records read.

## Results

- `none_seen`: looked, nothing out of place.
- `benign`: something odd with an innocent explanation; write the explanation.
- `unexplained`: something odd that nobody can explain yet; quote it.
- `concerning`: a strong sign that someone else has access; quote it.
- `na`: the check did not run.
