# watcher-sweep

**English** | [简体中文](README.zh-CN.md)

An agent skill for one of the most stressful questions a person can bring to an assistant: *"I think someone is watching me through my phone, computer or accounts."*

It turns that fear into a calm, consent-scoped sweep: a safety gate first, the person's signs mapped to the channels that could explain them, the cheap and likely places checked before the rare ones, every check recorded as done or not done, and an honest verdict that never says "clean". The next steps put evidence preservation and a safety plan before anything gets removed.

## Why

People who feel watched usually hear "you're being paranoid" or "wipe it all". The first ignores a real risk. The second destroys evidence and, when the watcher shares a home with the person, can alert them. Most real cases are explained by accounts (a known password, a forgotten linked session, a forwarding rule, location sharing), some by trackers, and fewer by device spyware. A good sweep reflects that order and is explicit about its limits.

## Features

- **Safety gate.** "In danger now" stops the sweep and points to help. Watcher closeness (`shared_home`, `knows_me`, `remote`, `state_level`, `unknown`) changes the advice.
- **Consent gate.** Refuses unless the owner authorised the sweep; refuses devices that belong to someone else.
- **Worry card.** Signs in the person's own words, dated, each mapped to `account`, `device`, `tracker` or `people`.
- **Generated check list.** Rows per account, per device kind (Android, iPhone, Windows, Mac, Linux), trackers, and an offline indicator scan for phones when a high-capability attacker is suspected.
- **Evidence rules.** Unexplained or concerning results must quote what was seen; benign results must name the innocent explanation; unrun checks need a reason.
- **Honest verdicts.** `NOTHING_FOUND_IN_SCOPE`, `LEAD`, `CONCERNING`, `INCOMPLETE`, `REFUSED/INVALID`, `SAFETY_FIRST`, each with its own exit code.
- **Safe ordering of next steps.** Preserve, then safety plan (when the watcher is close), then changes from a safe device, then the removal decision, then an expert for concerning findings.
- **Private report and minimal share summary.** The summary carries counts only.
- **Overclaim lint.** Flags "clean", "you're not being watched", "this proves", "nothing to worry about", "paranoid" and Chinese equivalents in anything you plan to show.
- Standard-library Python, no network access, 78 tests.

## Installation

The skill is the folder. Copy it where your agent looks for skills:

| agent | location |
|---|---|
| Claude Code | `~/.claude/skills/watcher-sweep/` (or `.claude/skills/` in a project) |
| Codex CLI | `~/.codex/skills/watcher-sweep/` |
| Cursor | `.cursor/skills/watcher-sweep/` in the project, or reference `SKILL.md` from your rules |
| Other agents | anywhere; point the agent at `SKILL.md` |

```bash
git clone https://github.com/fangdididi/watcher-sweep ~/.claude/skills/watcher-sweep
```

Python 3.8+ is all the helper script needs.

## Usage

Ask the agent something like "Someone seems to know what I write to my sister. Can you help me check my phone and accounts?" The agent follows `SKILL.md`. The script can also be used directly:

```bash
python3 scripts/sweep.py plan card.json > checks.csv        # starter check list
python3 scripts/sweep.py check card.json checks.csv         # verdict, exit code
python3 scripts/sweep.py report card.json checks.csv report.md
python3 scripts/sweep.py share card.json checks.csv         # counts only
python3 scripts/sweep.py lint message.txt                   # overclaim check
python3 -m unittest discover -s tests                       # run tests
```

## Example

```text
$ python3 scripts/sweep.py check examples/card.json examples/checks.csv
VERDICT CONCERNING
  concern: A-chat-linked_devices: Linked web session "Chrome (Windows)" active since 2026-10-02; person has never used chat on a computer
  lead: A-mail-password_known: Ex-partner set up this mail account in 2023 and chose the first password
  lead: D-phone-accessibility: Accessibility service "System Sync Service" is on; no app with that name in the launcher

$ python3 scripts/sweep.py lint examples/draft-message.txt
line 1: 'is clean' says the device or person is clean/safe
line 1: 'not being watched' states absence as fact
line 2: 'proves' claims certainty
3 overclaim(s)
```

The full private report is in `examples/report.md`.

## Boundaries

This skill does not install monitoring, does not check other people's devices, does not contact or browse indicator addresses, and does not replace a specialist. If someone may be in danger, contact local emergency services or a domestic-violence or digital-safety helpline first.

## File structure

```text
watcher-sweep/
├── SKILL.md                     # skill instructions (English)
├── SKILL.zh-CN.md               # skill instructions (Chinese)
├── README.md / README.zh-CN.md
├── LICENSE
├── scripts/sweep.py             # plan, check, report, share, lint
├── references/
│   ├── check-catalog.md         # what every check row means
│   └── check-catalog.zh-CN.md
├── examples/
│   ├── card.json                # worry card
│   ├── checks.csv               # filled sweep
│   ├── report.md                # private report
│   ├── share.txt                # minimal summary
│   └── draft-message.txt        # a message that fails the lint
└── tests/test_sweep.py          # 78 tests
```

## License

MIT
