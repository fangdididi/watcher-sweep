#!/usr/bin/env python3
"""watcher-sweep: turn a worry about being watched into a scoped, honest sweep.

Commands
  plan     CARD                 print a starter checks.csv for the devices/accounts on the card
  check    CARD CHECKS          validate and print the verdict (exit code = verdict)
  report   CARD CHECKS [OUT]    write the private Markdown report
  share    CARD CHECKS          print a minimal summary that is safe to share
  lint     FILE                 flag overclaiming language in any text you plan to show the person

Exit codes: 0 NOTHING_FOUND_IN_SCOPE, 1 LEAD, 2 CONCERNING, 3 INCOMPLETE,
            4 REFUSED/INVALID, 5 SAFETY_FIRST
Standard library only. Never touches the network or any device.
"""
import csv, io, json, re, sys

CHANNELS = {"account", "device", "tracker", "people"}
LAYER_FOR = {"account": {"account"}, "device": {"device", "indicator"}, "tracker": {"tracker"}, "people": set()}
LAYERS = {"account", "device", "tracker", "indicator"}
STATUSES = {"checked", "not_checked", "blocked"}
RESULTS = {"none_seen", "benign", "unexplained", "concerning", "na"}
CLOSENESS = {"shared_home", "knows_me", "remote", "state_level", "unknown"}
KINDS = {"android", "iphone", "windows", "mac", "linux"}
EXIT = {"NOTHING_FOUND_IN_SCOPE": 0, "LEAD": 1, "CONCERNING": 2, "INCOMPLETE": 3,
        "REFUSED": 4, "INVALID": 4, "SAFETY_FIRST": 5}
CLOSE_WATCHERS = {"shared_home", "knows_me", "unknown"}

MANDATORY = ("Nothing found in the checks listed here is not proof that nobody is watching. "
             "It only covers the items marked checked, on the date of the sweep.")

ACCOUNT_CHECKS = [
    ("sessions", "Signed-in sessions and devices list: every entry recognised"),
    ("recovery", "Recovery email and phone belong to the person and nobody else"),
    ("second_factor", "Second-step login method is on a device only the person holds"),
    ("forwarding", "Mail forwarding addresses and auto-filters: none unknown"),
    ("linked_devices", "Messaging apps' linked devices / web sessions: all recognised"),
    ("app_access", "Third-party apps with account access: all recognised"),
    ("sharing", "Location, calendar, photo and family sharing: only intended people"),
    ("password_known", "Has anyone else ever known or been told this password"),
]
DEVICE_CHECKS = {
    "android": [
        ("device_admin", "Device admin apps: none unrecognised"),
        ("accessibility", "Accessibility services turned on: all recognised"),
        ("notification_access", "Apps allowed to read notifications: all recognised"),
        ("unknown_sources", "Apps allowed to install other apps: none unexpected"),
        ("work_profile", "Work profile or management by an organisation: expected or absent"),
        ("app_list", "Full app list incl. system-looking names and hidden icons reviewed"),
        ("vpn_cert", "VPN profiles and user-installed certificates: none unknown"),
        ("store_scan", "Built-in app store malware scan is on and recently ran"),
    ],
    "iphone": [
        ("safety_check", "Built-in sharing and access review (e.g. Safety Check) walked through"),
        ("profiles", "Configuration profiles / device management: none unknown"),
        ("account_devices", "Devices signed into the Apple account: all recognised"),
        ("app_list", "App list reviewed, including unfamiliar utilities"),
        ("vpn_cert", "VPN configurations and trusted certificates: none unknown"),
        ("jailbreak_signs", "No unexpected package-manager style apps (sign of a jailbreak)"),
    ],
    "windows": [
        ("remote_tools", "Remote-access / screen-sharing software: none unrecognised"),
        ("startup", "Startup apps and scheduled tasks: none unrecognised"),
        ("extensions", "Browser extensions in every profile: all recognised"),
        ("local_accounts", "Local user accounts with admin rights: all recognised"),
        ("security_tool", "Built-in security tool is on and a full scan ran"),
    ],
    "mac": [
        ("remote_tools", "Remote-access / screen-sharing software and sharing settings"),
        ("login_items", "Login items and background items: none unrecognised"),
        ("extensions", "Browser extensions in every profile: all recognised"),
        ("privacy_grants", "Apps granted screen recording, accessibility, full disk access"),
        ("profiles", "Configuration profiles: none unknown"),
    ],
    "linux": [
        ("remote_tools", "SSH authorized keys and remote desktop services reviewed"),
        ("autostart", "Autostart entries, cron jobs and user services reviewed"),
        ("extensions", "Browser extensions in every profile: all recognised"),
    ],
}
TRACKER_CHECKS = [
    ("unknown_tracker_alert", "Phone's unknown-tracker alerts are on; any alert reviewed"),
    ("physical_look", "Bag, coat, car and gifts physically looked over for a small tracker"),
    ("map_sharing", "Live location sharing in map and family apps: only intended people"),
]
INDICATOR_CHECK = ("offline_indicator_scan",
                   "Offline indicator scan of a backup/collection with a trusted forensic toolkit")

OVERCLAIMS = [
    (r"\b(is|are|now|totally|completely|100%)\s+(clean|safe)\b", "says the device or person is clean/safe"),
    (r"\bno (spyware|stalkerware|malware|one is (watching|tracking))\b", "states absence as fact"),
    (r"\bnot being (watched|tracked|monitored|spied on)\b", "states absence as fact"),
    (r"\b(guarantee[ds]?|definitely|certainly|proves?|proven)\b", "claims certainty"),
    (r"\bnothing to worry about\b", "dismisses the worry"),
    (r"\bparanoi(d|a)\b", "labels the person"),
    (r"(没有|不存在)(间谍|监控|跟踪)(软件|器)?", "states absence as fact"),
    (r"(绝对|百分之百|完全)(安全|干净)", "claims certainty"),
    (r"已经安全", "says the person is safe"),
]


def load_card(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def load_checks(path):
    with open(path, encoding="utf-8", newline="") as f:
        return [{k.strip(): (v or "").strip() for k, v in row.items() if k} for row in csv.DictReader(f)]


def card_problems(card):
    """Return (gate, problems). gate is None, 'REFUSED' or 'SAFETY_FIRST'."""
    p = []
    if card.get("authorized_by_owner") is not True:
        return "REFUSED", ["the owner of these devices and accounts has not authorised this sweep"]
    for d in card.get("devices", []):
        if d.get("owner") not in ("self", "consented"):
            return "REFUSED", [f"device {d.get('id')} is not the person's own (owner must be self or consented)"]
    safety = card.get("safety") or {}
    if safety.get("in_danger_now") is True:
        return "SAFETY_FIRST", ["the person may be in danger right now: help first, sweep later"]
    if safety.get("watcher_closeness") not in CLOSENESS:
        p.append("safety.watcher_closeness must be one of " + ", ".join(sorted(CLOSENESS)))
    if "safe_device_available" not in safety:
        p.append("safety.safe_device_available must be answered (true/false)")
    signs = card.get("signs") or []
    if not signs:
        p.append("card needs at least one sign (what made the person worried)")
    ids = set()
    for s in signs:
        sid = s.get("id")
        if not sid or sid in ids:
            p.append(f"sign id missing or duplicated: {sid!r}")
        ids.add(sid)
        if not s.get("observation"):
            p.append(f"sign {sid} has no observation in the person's own words")
        ch = s.get("channels") or []
        if not ch:
            p.append(f"sign {sid} is not mapped to any channel")
        for c in ch:
            if c not in CHANNELS:
                p.append(f"sign {sid} has unknown channel {c!r}")
    dids = set()
    for d in card.get("devices", []):
        if d.get("kind") not in KINDS:
            p.append(f"device {d.get('id')} has unknown kind {d.get('kind')!r}")
        dids.add(d.get("id"))
    if not card.get("devices") and not card.get("accounts"):
        p.append("card lists no devices and no accounts to sweep")
    return None, p


def plan_rows(card):
    rows = []
    for a in card.get("accounts", []):
        for key, text in ACCOUNT_CHECKS:
            rows.append({"id": f"A-{a['id']}-{key}", "layer": "account", "target": a["id"], "check": text})
    for d in card.get("devices", []):
        for key, text in DEVICE_CHECKS.get(d.get("kind"), []):
            rows.append({"id": f"D-{d['id']}-{key}", "layer": "device", "target": d["id"], "check": text})
    for key, text in TRACKER_CHECKS:
        rows.append({"id": f"T-{key}", "layer": "tracker", "target": "person", "check": text})
    closeness = (card.get("safety") or {}).get("watcher_closeness")
    if closeness == "state_level":
        for d in card.get("devices", []):
            if d.get("kind") in ("android", "iphone"):
                rows.append({"id": f"I-{d['id']}", "layer": "indicator", "target": d["id"], "check": INDICATOR_CHECK[1]})
    for r in rows:
        r.update({"status": "not_checked", "result": "na", "evidence": "", "note": "", "explains": ""})
    return rows


def evaluate(card, rows):
    gate, problems = card_problems(card)
    out = {"verdict": None, "problems": problems, "gaps": [], "leads": [], "concerns": [],
           "unexplained_signs": [], "counts": {}}
    if gate:
        out["verdict"] = gate
        return out
    sign_ids = {s["id"] for s in card.get("signs", []) if s.get("id")}
    seen = set()
    for i, r in enumerate(rows, 1):
        rid = r.get("id") or f"row{i}"
        if rid in seen:
            problems.append(f"check id duplicated: {rid}")
        seen.add(rid)
        if r.get("layer") not in LAYERS:
            problems.append(f"{rid}: unknown layer {r.get('layer')!r}")
        st, res = r.get("status"), r.get("result")
        if st not in STATUSES:
            problems.append(f"{rid}: unknown status {st!r}")
        if res not in RESULTS:
            problems.append(f"{rid}: unknown result {res!r}")
        if st in ("not_checked", "blocked") and not r.get("note"):
            problems.append(f"{rid}: {st} needs a note saying why")
        if st in ("not_checked", "blocked") and res not in ("na", ""):
            problems.append(f"{rid}: a check that did not run cannot have result {res}")
        if st == "checked" and res == "na":
            problems.append(f"{rid}: checked but no result recorded")
        if res in ("unexplained", "concerning") and not r.get("evidence"):
            problems.append(f"{rid}: {res} needs the exact thing seen in evidence")
        if res == "benign" and not r.get("note"):
            problems.append(f"{rid}: benign needs a note naming the innocent explanation")
        for e in filter(None, (x.strip() for x in r.get("explains", "").split(";"))):
            if e not in sign_ids:
                problems.append(f"{rid}: explains unknown sign {e}")
    if problems:
        out["verdict"] = "INVALID"
        return out
    done = [r for r in rows if r["status"] == "checked"]
    out["counts"] = {s: sum(r["status"] == s for r in rows) for s in sorted(STATUSES)}
    out["counts"].update({x: sum(r["result"] == x for r in done) for x in ("none_seen", "benign", "unexplained", "concerning")})
    # coverage: each channel named by a sign needs a checked row in a matching layer
    for s in card.get("signs", []):
        for c in s.get("channels", []):
            layers = LAYER_FOR[c]
            if layers and not any(r["layer"] in layers for r in done):
                out["gaps"].append(f"sign {s['id']} points at '{c}' but no {'/'.join(sorted(layers))} check ran")
    for d in card.get("devices", []):
        if not any(r["target"] == d["id"] and r["layer"] in ("device", "indicator") for r in done):
            out["gaps"].append(f"device {d['id']} was never checked")
    for a in card.get("accounts", []):
        if not any(r["target"] == a["id"] and r["layer"] == "account" for r in done):
            out["gaps"].append(f"account {a['id']} was never checked")
    if card["safety"]["watcher_closeness"] == "state_level" and not any(r["layer"] == "indicator" for r in done):
        out["gaps"].append("high-capability watcher suspected but no offline indicator scan ran (consider an expert)")
    out["not_checked"] = [f"{r['id']}: {r['note']}" for r in rows if r["status"] != "checked"]
    out["leads"] = [f"{r['id']}: {r['evidence']}" for r in done if r["result"] == "unexplained"]
    out["concerns"] = [f"{r['id']}: {r['evidence']}" for r in done if r["result"] == "concerning"]
    explained = set()
    for r in done:
        if r["result"] in ("benign", "concerning", "unexplained"):
            explained |= {e.strip() for e in r.get("explains", "").split(";") if e.strip()}
    out["unexplained_signs"] = [s["id"] for s in card["signs"] if s["id"] not in explained]
    if out["concerns"]:
        out["verdict"] = "CONCERNING"
    elif out["leads"]:
        out["verdict"] = "LEAD"
    elif out["gaps"]:
        out["verdict"] = "INCOMPLETE"
    else:
        out["verdict"] = "NOTHING_FOUND_IN_SCOPE"
    return out


def next_steps(card, ev):
    v = ev["verdict"]
    safety = card.get("safety") or {}
    close = safety.get("watcher_closeness") in CLOSE_WATCHERS
    steps = []
    if v == "SAFETY_FIRST":
        return ["Contact local emergency services or a domestic-violence / digital-safety helpline now.",
                "Do not change settings or remove apps yet: the watcher may notice.",
                "Come back to the sweep once the person is somewhere safe."]
    if v in ("CONCERNING", "LEAD"):
        steps.append("Preserve first: photograph or screenshot each finding with date and time before changing anything.")
        if close:
            steps.append("Make a safety plan with an advocate or helpline before removing anything; removal can alert the watcher.")
        if not safety.get("safe_device_available"):
            steps.append("Get access to a device the watcher has never touched before changing passwords.")
        steps.append("From the safe device: change passwords, sign out other sessions, replace recovery details and second-step methods.")
        steps.append("Only then decide with the person whether and when to remove the app, profile or tracker.")
        if v == "CONCERNING" or safety.get("watcher_closeness") == "state_level":
            steps.append("Ask a qualified digital-security helpline or forensic lab to confirm; keep the device powered and unmodified for them.")
    elif v == "INCOMPLETE":
        steps.append("Close the gaps listed above, or tell the person plainly which parts were not looked at.")
    else:
        steps.append("Keep the habits that matter: unique passwords, second-step login on a device only you hold, updates on.")
        steps.append("Re-run the sweep if new signs appear; note the date and what happened each time.")
    if ev.get("unexplained_signs") and v != "INCOMPLETE":
        steps.append("Some signs are still not explained by any finding: " + ", ".join(ev["unexplained_signs"]) + ".")
    return steps


def render_report(card, rows, ev):
    L = [f"# Watcher sweep: {card.get('title', 'private report')}", "",
         f"Date: {card.get('date', 'not given')}  ", f"Verdict: **{ev['verdict']}**", "", f"> {MANDATORY}", ""]
    if ev["verdict"] in ("REFUSED", "INVALID", "SAFETY_FIRST"):
        L += ["## Why the sweep stopped", ""] + [f"- {p}" for p in ev["problems"]] + [""]
    else:
        L += ["## Signs the person reported", ""]
        for s in card["signs"]:
            mark = "still unexplained" if s["id"] in ev["unexplained_signs"] else "linked to a finding"
            L.append(f"- {s['id']} ({s.get('seen', 'date unknown')}): {s['observation']} [{', '.join(s['channels'])}; {mark}]")
        L += ["", "## What was checked", "", "| id | layer | target | status | result | evidence / note |", "|---|---|---|---|---|---|"]
        for r in rows:
            txt = (r.get("evidence") or r.get("note") or "").replace("|", "/")
            L.append(f"| {r['id']} | {r['layer']} | {r['target']} | {r['status']} | {r['result']} | {txt} |")
        for title, key in (("Concerning findings", "concerns"), ("Leads to follow up", "leads"),
                           ("Coverage gaps", "gaps"), ("Not checked", "not_checked")):
            if ev.get(key):
                L += ["", f"## {title}", ""] + [f"- {x}" for x in ev[key]]
    L += ["", "## Next steps, in this order", ""] + [f"{i}. {s}" for i, s in enumerate(next_steps(card, ev), 1)]
    L += ["", "Keep this report private. Share the short summary instead unless the person decides otherwise.", ""]
    return "\n".join(L)


def share_summary(card, ev):
    c = ev.get("counts", {})
    return "\n".join([
        f"Watcher sweep summary ({card.get('date', 'date not given')})",
        f"Verdict: {ev['verdict']}",
        f"Checks run: {c.get('checked', 0)}, not run: {c.get('not_checked', 0) + c.get('blocked', 0)}",
        f"Concerning: {c.get('concerning', 0)}, leads: {c.get('unexplained', 0)}, gaps: {len(ev.get('gaps', []))}",
        MANDATORY])


def lint_text(text):
    hits = []
    for n, line in enumerate(text.splitlines(), 1):
        if MANDATORY[:40] in line:
            continue
        for pat, why in OVERCLAIMS:
            for m in re.finditer(pat, line, re.I):
                hits.append((n, m.group(0), why))
    return hits


def main(argv):
    if len(argv) < 2:
        print(__doc__)
        return 4
    cmd = argv[1]
    if cmd == "lint" and len(argv) == 3:
        hits = lint_text(open(argv[2], encoding="utf-8").read())
        for n, frag, why in hits:
            print(f"line {n}: '{frag}' {why}")
        print("OK: no overclaims" if not hits else f"{len(hits)} overclaim(s)")
        return 1 if hits else 0
    if cmd == "plan" and len(argv) == 3:
        card = load_card(argv[2])
        gate, probs = card_problems(card)
        if gate:
            print(gate + ": " + "; ".join(probs))
            return EXIT[gate]
        buf = io.StringIO()
        w = csv.DictWriter(buf, fieldnames=["id", "layer", "target", "check", "status", "result", "evidence", "note", "explains"])
        w.writeheader()
        w.writerows(plan_rows(card))
        sys.stdout.write(buf.getvalue())
        return 0
    if cmd in ("check", "report", "share") and len(argv) >= 4:
        card, rows = load_card(argv[2]), load_checks(argv[3])
        ev = evaluate(card, rows)
        if cmd == "check":
            print("VERDICT", ev["verdict"])
            for k in ("problems", "concerns", "leads", "gaps"):
                for x in ev.get(k) or []:
                    print(f"  {k[:-1]}: {x}")
            if ev.get("unexplained_signs"):
                print("  signs still unexplained:", ", ".join(ev["unexplained_signs"]))
        elif cmd == "report":
            text = render_report(card, rows, ev)
            if len(argv) > 4:
                open(argv[4], "w", encoding="utf-8").write(text)
                print("wrote", argv[4])
            else:
                print(text)
        else:
            print(share_summary(card, ev))
        return EXIT[ev["verdict"]]
    print(__doc__)
    return 4


if __name__ == "__main__":
    sys.exit(main(sys.argv))
