import copy, csv, json, os, subprocess, sys, tempfile, unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import sweep  # noqa: E402

EX = os.path.join(ROOT, "examples")


def card(**over):
    c = {
        "date": "2026-10-28", "authorized_by_owner": True,
        "safety": {"in_danger_now": False, "watcher_closeness": "remote", "safe_device_available": True},
        "signs": [{"id": "S1", "observation": "odd login email", "channels": ["account"]}],
        "devices": [{"id": "p", "kind": "iphone", "owner": "self"}],
        "accounts": [{"id": "m", "kind": "email"}],
    }
    c.update(over)
    return c


def row(rid, layer, target, status="checked", result="none_seen", evidence="", note="", explains=""):
    return {"id": rid, "layer": layer, "target": target, "check": "x", "status": status,
            "result": result, "evidence": evidence, "note": note, "explains": explains}


def full_rows():
    return [row("a1", "account", "m"), row("d1", "device", "p"), row("t1", "tracker", "person")]


class Gates(unittest.TestCase):
    def test_unauthorised_refused(self):
        self.assertEqual(sweep.evaluate(card(authorized_by_owner=False), full_rows())["verdict"], "REFUSED")

    def test_missing_authorisation_refused(self):
        c = card(); del c["authorized_by_owner"]
        self.assertEqual(sweep.evaluate(c, full_rows())["verdict"], "REFUSED")

    def test_someone_elses_device_refused(self):
        c = card(devices=[{"id": "p", "kind": "android", "owner": "partner"}])
        self.assertEqual(sweep.evaluate(c, full_rows())["verdict"], "REFUSED")

    def test_consented_device_allowed(self):
        c = card(devices=[{"id": "p", "kind": "android", "owner": "consented"}])
        self.assertNotEqual(sweep.evaluate(c, full_rows())["verdict"], "REFUSED")

    def test_danger_now_stops(self):
        c = card(); c["safety"]["in_danger_now"] = True
        self.assertEqual(sweep.evaluate(c, full_rows())["verdict"], "SAFETY_FIRST")

    def test_safety_first_steps_say_do_not_change(self):
        c = card(); c["safety"]["in_danger_now"] = True
        steps = sweep.next_steps(c, sweep.evaluate(c, []))
        self.assertTrue(any("Do not change" in s for s in steps))

    def test_refusal_beats_danger(self):
        c = card(authorized_by_owner=False); c["safety"]["in_danger_now"] = True
        self.assertEqual(sweep.evaluate(c, [])["verdict"], "REFUSED")


class CardValidation(unittest.TestCase):
    def v(self, c):
        return sweep.evaluate(c, full_rows())

    def test_bad_closeness(self):
        c = card(); c["safety"]["watcher_closeness"] = "neighbour"
        self.assertEqual(self.v(c)["verdict"], "INVALID")

    def test_safe_device_must_be_answered(self):
        c = card(); del c["safety"]["safe_device_available"]
        self.assertEqual(self.v(c)["verdict"], "INVALID")

    def test_no_signs(self):
        self.assertEqual(self.v(card(signs=[]))["verdict"], "INVALID")

    def test_sign_without_channel(self):
        self.assertEqual(self.v(card(signs=[{"id": "S1", "observation": "x", "channels": []}]))["verdict"], "INVALID")

    def test_sign_unknown_channel(self):
        self.assertEqual(self.v(card(signs=[{"id": "S1", "observation": "x", "channels": ["wifi"]}]))["verdict"], "INVALID")

    def test_sign_without_observation(self):
        self.assertEqual(self.v(card(signs=[{"id": "S1", "channels": ["account"]}]))["verdict"], "INVALID")

    def test_duplicate_sign_ids(self):
        s = {"id": "S1", "observation": "x", "channels": ["account"]}
        self.assertEqual(self.v(card(signs=[s, dict(s)]))["verdict"], "INVALID")

    def test_unknown_device_kind(self):
        self.assertEqual(self.v(card(devices=[{"id": "p", "kind": "fridge", "owner": "self"}]))["verdict"], "INVALID")

    def test_nothing_to_sweep(self):
        self.assertEqual(self.v(card(devices=[], accounts=[]))["verdict"], "INVALID")


class RowValidation(unittest.TestCase):
    def v(self, rows):
        return sweep.evaluate(card(), rows)

    def test_duplicate_ids(self):
        r = full_rows(); r.append(row("a1", "account", "m"))
        self.assertIn("duplicated", " ".join(self.v(r)["problems"]))

    def test_unknown_layer(self):
        r = full_rows(); r.append(row("x", "router", "m"))
        self.assertEqual(self.v(r)["verdict"], "INVALID")

    def test_unknown_status(self):
        r = full_rows(); r[0]["status"] = "done"
        self.assertEqual(self.v(r)["verdict"], "INVALID")

    def test_unknown_result(self):
        r = full_rows(); r[0]["result"] = "fine"
        self.assertEqual(self.v(r)["verdict"], "INVALID")

    def test_not_checked_needs_note(self):
        r = full_rows(); r.append(row("x", "device", "p", status="not_checked", result="na"))
        self.assertEqual(self.v(r)["verdict"], "INVALID")

    def test_blocked_needs_note(self):
        r = full_rows(); r.append(row("x", "device", "p", status="blocked", result="na"))
        self.assertEqual(self.v(r)["verdict"], "INVALID")

    def test_unrun_check_cannot_have_result(self):
        r = full_rows(); r.append(row("x", "device", "p", status="not_checked", result="none_seen", note="later"))
        self.assertEqual(self.v(r)["verdict"], "INVALID")

    def test_checked_needs_result(self):
        r = full_rows(); r[0]["result"] = "na"
        self.assertEqual(self.v(r)["verdict"], "INVALID")

    def test_unexplained_needs_evidence(self):
        r = full_rows(); r[0]["result"] = "unexplained"
        self.assertEqual(self.v(r)["verdict"], "INVALID")

    def test_concerning_needs_evidence(self):
        r = full_rows(); r[0]["result"] = "concerning"
        self.assertEqual(self.v(r)["verdict"], "INVALID")

    def test_benign_needs_note(self):
        r = full_rows(); r[0]["result"] = "benign"
        self.assertEqual(self.v(r)["verdict"], "INVALID")

    def test_explains_unknown_sign(self):
        r = full_rows(); r[0].update(result="benign", note="old tablet", explains="S9")
        self.assertEqual(self.v(r)["verdict"], "INVALID")


class Verdicts(unittest.TestCase):
    def test_nothing_found(self):
        self.assertEqual(sweep.evaluate(card(), full_rows())["verdict"], "NOTHING_FOUND_IN_SCOPE")

    def test_never_says_clean(self):
        self.assertNotIn("CLEAN", sweep.EXIT)

    def test_lead(self):
        r = full_rows(); r[1].update(result="unexplained", evidence="profile 'Sync' installed")
        self.assertEqual(sweep.evaluate(card(), r)["verdict"], "LEAD")

    def test_concerning_beats_lead(self):
        r = full_rows()
        r[1].update(result="unexplained", evidence="a")
        r[0].update(result="concerning", evidence="b")
        self.assertEqual(sweep.evaluate(card(), r)["verdict"], "CONCERNING")

    def test_lead_beats_gaps(self):
        r = [row("a1", "account", "m", result="unexplained", evidence="unknown session")]
        self.assertEqual(sweep.evaluate(card(), r)["verdict"], "LEAD")

    def test_device_never_checked_is_gap(self):
        ev = sweep.evaluate(card(), [row("a1", "account", "m")])
        self.assertEqual(ev["verdict"], "INCOMPLETE")
        self.assertTrue(any("device p" in g for g in ev["gaps"]))

    def test_account_never_checked_is_gap(self):
        ev = sweep.evaluate(card(), [row("d1", "device", "p")])
        self.assertTrue(any("account m" in g for g in ev["gaps"]))

    def test_not_checked_row_does_not_count_as_coverage(self):
        r = [row("a1", "account", "m", status="not_checked", result="na", note="no password"), row("d1", "device", "p")]
        self.assertEqual(sweep.evaluate(card(), r)["verdict"], "INCOMPLETE")

    def test_sign_channel_without_layer_is_gap(self):
        c = card(signs=[{"id": "S1", "observation": "x", "channels": ["tracker"]}])
        ev = sweep.evaluate(c, [row("a1", "account", "m"), row("d1", "device", "p")])
        self.assertTrue(any("tracker" in g for g in ev["gaps"]))

    def test_people_channel_needs_no_technical_check(self):
        c = card(signs=[{"id": "S1", "observation": "x", "channels": ["people"]}])
        self.assertEqual(sweep.evaluate(c, [row("a1", "account", "m"), row("d1", "device", "p")])["verdict"], "NOTHING_FOUND_IN_SCOPE")

    def test_indicator_counts_for_device(self):
        ev = sweep.evaluate(card(), [row("a1", "account", "m"), row("i1", "indicator", "p"), row("t", "tracker", "person")])
        self.assertEqual(ev["verdict"], "NOTHING_FOUND_IN_SCOPE")

    def test_state_level_requires_indicator_scan(self):
        c = card(); c["safety"]["watcher_closeness"] = "state_level"
        ev = sweep.evaluate(c, full_rows())
        self.assertEqual(ev["verdict"], "INCOMPLETE")
        self.assertTrue(any("indicator" in g for g in ev["gaps"]))

    def test_state_level_with_indicator_scan(self):
        c = card(); c["safety"]["watcher_closeness"] = "state_level"
        self.assertEqual(sweep.evaluate(c, full_rows() + [row("i1", "indicator", "p")])["verdict"], "NOTHING_FOUND_IN_SCOPE")

    def test_unexplained_signs_listed(self):
        self.assertEqual(sweep.evaluate(card(), full_rows())["unexplained_signs"], ["S1"])

    def test_benign_explains_sign(self):
        r = full_rows(); r[0].update(result="benign", note="her own laptop", explains="S1")
        self.assertEqual(sweep.evaluate(card(), r)["unexplained_signs"], [])

    def test_counts(self):
        r = full_rows() + [row("x", "device", "p", status="blocked", result="na", note="locked")]
        c = sweep.evaluate(card(), r)["counts"]
        self.assertEqual((c["checked"], c["blocked"], c["none_seen"]), (3, 1, 3))


class Plan(unittest.TestCase):
    def test_rows_per_account_and_device(self):
        rows = sweep.plan_rows(card())
        self.assertEqual(sum(r["layer"] == "account" for r in rows), len(sweep.ACCOUNT_CHECKS))
        self.assertEqual(sum(r["layer"] == "device" for r in rows), len(sweep.DEVICE_CHECKS["iphone"]))

    def test_tracker_rows_always_present(self):
        self.assertEqual(sum(r["layer"] == "tracker" for r in sweep.plan_rows(card())), len(sweep.TRACKER_CHECKS))

    def test_indicator_only_for_state_level_phones(self):
        self.assertFalse(any(r["layer"] == "indicator" for r in sweep.plan_rows(card())))
        c = card(); c["safety"]["watcher_closeness"] = "state_level"
        self.assertTrue(any(r["layer"] == "indicator" for r in sweep.plan_rows(c)))

    def test_indicator_not_for_laptops(self):
        c = card(devices=[{"id": "l", "kind": "windows", "owner": "self"}]); c["safety"]["watcher_closeness"] = "state_level"
        self.assertFalse(any(r["layer"] == "indicator" for r in sweep.plan_rows(c)))

    def test_plan_starts_unchecked(self):
        self.assertTrue(all(r["status"] == "not_checked" and r["result"] == "na" for r in sweep.plan_rows(card())))

    def test_unfilled_plan_is_invalid_until_notes(self):
        self.assertEqual(sweep.evaluate(card(), sweep.plan_rows(card()))["verdict"], "INVALID")

    def test_every_kind_has_checks(self):
        for k in sweep.KINDS:
            self.assertTrue(sweep.DEVICE_CHECKS[k])

    def test_ids_unique(self):
        ids = [r["id"] for r in sweep.plan_rows(card(accounts=[{"id": "m"}, {"id": "n"}]))]
        self.assertEqual(len(ids), len(set(ids)))


class Steps(unittest.TestCase):
    def ev(self, c, result):
        r = full_rows(); r[1].update(result=result, evidence="e")
        return sweep.evaluate(c, r)

    def test_preserve_comes_first(self):
        c = card()
        self.assertTrue(sweep.next_steps(c, self.ev(c, "concerning"))[0].startswith("Preserve"))

    def test_close_watcher_gets_safety_plan_before_removal(self):
        c = card(); c["safety"]["watcher_closeness"] = "shared_home"
        steps = sweep.next_steps(c, self.ev(c, "unexplained"))
        plan = next(i for i, s in enumerate(steps) if "safety plan" in s)
        remove = next(i for i, s in enumerate(steps) if "remove" in s and "decide" in s)
        self.assertLess(plan, remove)

    def test_remote_watcher_no_safety_plan_step(self):
        c = card()
        self.assertFalse(any("safety plan" in s for s in sweep.next_steps(c, self.ev(c, "unexplained"))))

    def test_no_safe_device_step(self):
        c = card(); c["safety"]["safe_device_available"] = False
        self.assertTrue(any("never touched" in s for s in sweep.next_steps(c, self.ev(c, "concerning"))))

    def test_concerning_points_to_expert(self):
        c = card()
        self.assertTrue(any("forensic" in s for s in sweep.next_steps(c, self.ev(c, "concerning"))))

    def test_incomplete_step(self):
        c = card()
        ev = sweep.evaluate(c, [row("a1", "account", "m")])
        self.assertIn("gaps", sweep.next_steps(c, ev)[0])


class Lint(unittest.TestCase):
    def test_flags_clean(self):
        self.assertTrue(sweep.lint_text("Your phone is clean."))

    def test_flags_absence(self):
        self.assertTrue(sweep.lint_text("There is no spyware here."))

    def test_flags_not_being_watched(self):
        self.assertTrue(sweep.lint_text("You are not being watched."))

    def test_flags_certainty(self):
        self.assertTrue(sweep.lint_text("This proves nothing is wrong"))

    def test_flags_dismissal(self):
        self.assertTrue(sweep.lint_text("nothing to worry about"))

    def test_flags_label(self):
        self.assertTrue(sweep.lint_text("don't be paranoid"))

    def test_flags_chinese(self):
        self.assertTrue(sweep.lint_text("你的手机绝对安全"))
        self.assertTrue(sweep.lint_text("没有间谍软件"))

    def test_allows_honest_text(self):
        self.assertFalse(sweep.lint_text("No matches were found in the 10 checks we ran today."))

    def test_mandatory_line_passes(self):
        self.assertFalse(sweep.lint_text(sweep.MANDATORY))


class Rendering(unittest.TestCase):
    def test_report_has_mandatory_line(self):
        self.assertIn(sweep.MANDATORY, sweep.render_report(card(), full_rows(), sweep.evaluate(card(), full_rows())))

    def test_report_passes_lint(self):
        txt = sweep.render_report(card(), full_rows(), sweep.evaluate(card(), full_rows()))
        self.assertFalse(sweep.lint_text(txt))

    def test_refused_report_explains(self):
        c = card(authorized_by_owner=False)
        self.assertIn("Why the sweep stopped", sweep.render_report(c, [], sweep.evaluate(c, [])))

    def test_share_has_no_evidence(self):
        r = full_rows(); r[0].update(result="concerning", evidence="SECRET-DETAIL")
        self.assertNotIn("SECRET-DETAIL", sweep.share_summary(card(), sweep.evaluate(card(), r)))

    def test_pipe_escaped(self):
        r = full_rows(); r[0].update(result="unexplained", evidence="a|b")
        self.assertIn("a/b", sweep.render_report(card(), r, sweep.evaluate(card(), r)))


class Cli(unittest.TestCase):
    def run_cli(self, *args):
        return subprocess.run([sys.executable, os.path.join(ROOT, "scripts", "sweep.py"), *args], capture_output=True, text=True)

    def test_example_is_concerning(self):
        p = self.run_cli("check", os.path.join(EX, "card.json"), os.path.join(EX, "checks.csv"))
        self.assertEqual(p.returncode, 2)
        self.assertIn("CONCERNING", p.stdout)

    def test_plan_cli(self):
        p = self.run_cli("plan", os.path.join(EX, "card.json"))
        self.assertEqual(p.returncode, 0)
        self.assertTrue(p.stdout.startswith("id,layer"))

    def test_plan_refused(self):
        with tempfile.TemporaryDirectory() as d:
            f = os.path.join(d, "c.json")
            with open(f, "w") as fh:
                json.dump(card(authorized_by_owner=False), fh)
            self.assertEqual(self.run_cli("plan", f).returncode, 4)

    def test_lint_cli_exit(self):
        self.assertEqual(self.run_cli("lint", os.path.join(EX, "draft-message.txt")).returncode, 1)
        self.assertEqual(self.run_cli("lint", os.path.join(EX, "report.md")).returncode, 0)

    def test_report_cli_writes(self):
        with tempfile.TemporaryDirectory() as d:
            out = os.path.join(d, "r.md")
            self.run_cli("report", os.path.join(EX, "card.json"), os.path.join(EX, "checks.csv"), out)
            with open(out) as fh:
                self.assertTrue(fh.read().startswith("# Watcher sweep"))

    def test_usage(self):
        self.assertEqual(self.run_cli().returncode, 4)
        self.assertEqual(self.run_cli("bogus").returncode, 4)


if __name__ == "__main__":
    unittest.main()
