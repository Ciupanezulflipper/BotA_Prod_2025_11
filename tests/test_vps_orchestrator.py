from __future__ import annotations

import importlib.util
import io
import json
import os
import shlex
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("vps_orchestrator_tests", ROOT / "tools/vps_orchestrator.py")
assert SPEC and SPEC.loader
vps = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = vps
SPEC.loader.exec_module(vps)


def wait_until(predicate, timeout=5.0):
    until = time.monotonic() + timeout
    while time.monotonic() < until:
        value = predicate()
        if value:
            return value
        time.sleep(0.01)
    raise AssertionError("condition timed out")


class OrchestratorTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.mutable = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def orch(self, jobs=(), grace=0.1):
        return vps.Orchestrator(ROOT, self.mutable, jobs, term_grace=grace)

    def job(self, name, code, deadline=2.0):
        return vps.Job(name, ((sys.executable, "-c", code),), vps.EVERY_MINUTE, deadline)

    def launch_wait(self, orch, job):
        self.assertTrue(orch.launch(job, datetime.now(timezone.utc)))
        wait_until(lambda: job.name not in orch.active_jobs)
        return orch.latest[job.name]

    def test_second_instance_rejected(self):
        first, second = self.orch(), self.orch()
        first.acquire_instance_lock()
        with self.assertRaises(vps.InstanceLocked):
            second.acquire_instance_lock()
        first.shutdown()

    def test_second_command_invocation_is_rejected_immediately(self):
        holder_code = (
            "import signal; from pathlib import Path; from tools.vps_orchestrator import Orchestrator; "
            f"o=Orchestrator(Path({str(ROOT)!r}),Path({str(self.mutable)!r}),()); "
            "signal.signal(signal.SIGTERM,lambda s,f:o.stop_event.set()); raise SystemExit(o.run())"
        )
        holder = subprocess.Popen([sys.executable, "-c", holder_code], cwd=ROOT,
                                  stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                  stderr=subprocess.PIPE)
        wait_until(lambda: (self.mutable / "state" / vps.HEALTH_FILENAME).exists())
        env = dict(os.environ, BOTA_CODE_ROOT=str(ROOT), BOTA_MUTABLE_ROOT=str(self.mutable))
        rejected = subprocess.run([sys.executable, str(ROOT / "tools" / "vps_orchestrator.py")],
                                  cwd=ROOT, env=env, stdin=subprocess.DEVNULL,
                                  stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=3)
        self.assertEqual(rejected.returncode, 73)
        self.assertIn(b"another VPS orchestrator instance", rejected.stderr)
        holder.send_signal(signal.SIGTERM)
        self.assertEqual(holder.wait(timeout=3), 0)

    def test_child_has_own_process_group_and_success_is_reaped(self):
        orch = self.orch()
        job = self.job("ok", "import time; time.sleep(.15)")
        orch.launch(job, datetime.now(timezone.utc))
        child = wait_until(lambda: orch.running.get("ok"))
        self.assertEqual(os.getpgid(child.pid), child.pid)
        wait_until(lambda: "ok" not in orch.active_jobs)
        self.assertIsNotNone(child.returncode)
        self.assertEqual(orch.latest["ok"]["status"], "PASS")

    def test_crash_records_failed_and_next_job_survives(self):
        orch = self.orch()
        failed = self.launch_wait(orch, self.job("bad", "raise SystemExit(7)"))
        passed = self.launch_wait(orch, self.job("good", "pass"))
        self.assertEqual((failed["status"], failed["exit_code"]), ("FAILED", 7))
        self.assertEqual(passed["status"], "PASS")

    def test_hung_process_group_gets_term_then_kill_and_is_gone(self):
        pid_path = self.mutable / "pids"
        term_path = self.mutable / "term_seen"
        code = (
            "import os,signal,subprocess,sys,time,pathlib; "
            f"signal.signal(signal.SIGTERM, lambda s,f:pathlib.Path({str(term_path)!r}).write_text('TERM')); "
            "c=subprocess.Popen([sys.executable,'-c','import signal,time; signal.signal(signal.SIGTERM,signal.SIG_IGN); time.sleep(99)']); "
            f"pathlib.Path({str(pid_path)!r}).write_text(str(os.getpid())+' '+str(c.pid)); time.sleep(99)"
        )
        orch = self.orch(grace=0.05)
        result = self.launch_wait(orch, self.job("hung", code, 0.15))
        self.assertEqual(result["status"], "TIMED_OUT")
        self.assertEqual(term_path.read_text(), "TERM")
        for pid in map(int, pid_path.read_text().split()):
            with self.assertRaises(ProcessLookupError):
                os.kill(pid, 0)

    def test_overlap_is_skipped_without_duplicate(self):
        orch = self.orch()
        job = self.job("slow", "import time; time.sleep(.2)")
        now = datetime.now(timezone.utc)
        self.assertTrue(orch.launch(job, now))
        self.assertFalse(orch.launch(job, now))
        self.assertEqual(orch.latest["slow"]["status"], "SKIPPED_OVERLAP")
        wait_until(lambda: "slow" not in orch.active_jobs)

    def test_launch_error_is_terminal_and_does_not_break_orchestrator(self):
        orch = self.orch()
        missing = vps.Job("missing", (("/definitely/not/a/program",),),
                          vps.EVERY_MINUTE, 1)
        self.assertEqual(self.launch_wait(orch, missing)["status"], "LAUNCH_ERROR")
        self.assertEqual(self.launch_wait(orch, self.job("after", "pass"))["status"], "PASS")

    def test_cadence_boundaries_and_no_completion_drift(self):
        base = datetime(2026, 8, 23, 12, 12, 59, tzinfo=timezone.utc)
        expected = ((vps.EVERY_MINUTE, (12, 13)), (vps.EVERY_5_MINUTES, (12, 15)),
                    (vps.EVERY_15_MINUTES, (12, 15)), (vps.UPDATER_MINUTES, (12, 13)),
                    (vps.EVERY_30_MINUTES, (12, 30)))
        for cadence, hour_minute in expected:
            due = cadence.next_after(base)
            self.assertEqual((due.hour, due.minute), hour_minute)
        scheduled = datetime(2026, 8, 23, 12, 15, tzinfo=timezone.utc)
        self.assertEqual(vps.EVERY_5_MINUTES.next_after(scheduled).minute, 20)

    def test_reporting_cadence_boundaries_are_exact_utc(self):
        cases = (
            (vps.DAILY_0506, datetime(2026, 8, 24, 5, 5, 59, tzinfo=timezone.utc),
             datetime(2026, 8, 24, 5, 6, tzinfo=timezone.utc)),
            (vps.HOURLY_MINUTE_04, datetime(2026, 8, 24, 12, 3, 59, tzinfo=timezone.utc),
             datetime(2026, 8, 24, 12, 4, tzinfo=timezone.utc)),
            (vps.SUNDAY_0100, datetime(2026, 8, 22, 23, 0, tzinfo=timezone.utc),
             datetime(2026, 8, 23, 1, 0, tzinfo=timezone.utc)),
            (vps.HOURLY_MINUTE_10, datetime(2026, 8, 24, 12, 9, 59, tzinfo=timezone.utc),
             datetime(2026, 8, 24, 12, 10, tzinfo=timezone.utc)),
        )
        for cadence, moment, expected in cases:
            self.assertEqual(cadence.next_after(moment), expected)

    def test_same_boundary_jobs_run_independently_and_overlap_stays_per_job(self):
        orch = self.orch()
        alerts = self.job("alerts_to_trades", "import time; time.sleep(.15)")
        pause = self.job("pause_guard", "import time; time.sleep(.15)")
        now = datetime.now(timezone.utc)
        self.assertTrue(orch.launch(alerts, now))
        self.assertTrue(orch.launch(pause, now))
        self.assertFalse(orch.launch(alerts, now))
        wait_until(lambda: not orch.active_jobs)
        self.assertEqual(orch.latest["alerts_to_trades"]["status"], "PASS")
        self.assertEqual(orch.latest["pause_guard"]["status"], "PASS")

    def test_shutdown_kills_all_active_groups(self):
        orch = self.orch(grace=0.05)
        jobs = [self.job(name, "import time; time.sleep(99)", 100) for name in ("a", "b")]
        for job in jobs:
            orch.launch(job, datetime.now(timezone.utc))
        children = wait_until(lambda: list(orch.running.values()) if len(orch.running) == 2 else None)
        orch.shutdown()
        self.assertEqual(orch.lifecycle, "STOPPED")
        for child in children:
            self.assertIsNotNone(child.returncode)
            with self.assertRaises(ProcessLookupError):
                os.kill(child.pid, 0)

    def test_sigterm_stops_orchestrator_and_its_child_group(self):
        child_pid = self.mutable / "child_pid"
        child_code = f"import os,pathlib,time; pathlib.Path({str(child_pid)!r}).write_text(str(os.getpid())); time.sleep(99)"
        holder_code = (
            "import signal,sys; from datetime import datetime,timezone; from pathlib import Path; "
            "from tools.vps_orchestrator import Orchestrator,Job,EVERY_MINUTE; "
            f"j=Job('safe',((sys.executable,'-c',{child_code!r}),),EVERY_MINUTE,100); "
            f"o=Orchestrator(Path({str(ROOT)!r}),Path({str(self.mutable)!r}),(j,),term_grace=.05); "
            "signal.signal(signal.SIGTERM,lambda s,f:o.stop_event.set()); raise SystemExit(o.run())"
        )
        holder = subprocess.Popen([sys.executable, "-c", holder_code], cwd=ROOT,
                                  stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                  stderr=subprocess.PIPE)
        wait_until(child_pid.exists)
        pid = int(child_pid.read_text())
        holder.send_signal(signal.SIGTERM)
        self.assertEqual(holder.wait(timeout=3), 0)
        health = json.loads((self.mutable / "state" / vps.HEALTH_FILENAME).read_text())
        self.assertEqual(health["lifecycle"], "STOPPED")
        with self.assertRaises(ProcessLookupError):
            os.kill(pid, 0)

    def test_evidence_restart_identity_policy_and_environment(self):
        output = self.mutable / "environment.json"
        keys = ["BOTA_CODE_ROOT", "BOTA_ROOT", "BOTA_MUTABLE_ROOT", *vps.POLICY_KEYS]
        code = f"import json,os,pathlib; pathlib.Path({str(output)!r}).write_text(json.dumps({{k:os.environ[k] for k in {keys!r}}}))"
        os.environ["POLICY_B_SCORE_MIN"] = "hostile"
        first = self.orch()
        result = self.launch_wait(first, self.job("env", code))
        self.assertEqual(result["status"], "PASS")
        persisted = json.loads(first.health_path.read_text())
        second = self.orch()
        self.assertNotEqual(first.runtime_instance_id, second.runtime_instance_id)
        self.assertEqual(second.health()["previous_instance"]["runtime_instance_id"],
                         first.runtime_instance_id)
        self.assertEqual(second.health()["previous_instance"]["useful_progress"]["env"]["status"], "PASS")
        self.assertEqual(persisted["policy_fingerprint"], first.policy_fingerprint)
        self.assertEqual(persisted["useful_progress"]["env"]["status"], "PASS")
        env = json.loads(output.read_text())
        self.assertEqual(env["BOTA_CODE_ROOT"], str(ROOT))
        self.assertEqual(env["BOTA_ROOT"], str(ROOT))
        self.assertEqual(env["BOTA_MUTABLE_ROOT"], str(self.mutable))
        self.assertEqual(env["POLICY_B_SCORE_MIN"], "70")

    def test_manifest_backed_release_identity_and_malformed_fail_closed(self):
        sha = "a" * 40
        release = self.mutable / sha
        (release / "config").mkdir(parents=True)
        for relative in ("pyproject.toml", "requirements-runtime.txt", "config/production-vps.env"):
            target = release / relative
            target.write_bytes((ROOT / relative).read_bytes())
        fingerprint = vps.effective_config_evidence(
            policy_path=release / "config/production-vps.env",
            dependency_path=release / "requirements-runtime.txt",
            pyproject_path=release / "pyproject.toml")["fingerprint_sha256"]
        manifest = {"schema_version": "1.0", "git_commit_sha": sha,
                    "git_tree_sha": "b" * 40,
                    "effective_config_fingerprint": fingerprint}
        (release / vps.RELEASE_MANIFEST_FILENAME).write_text(json.dumps(manifest))
        (release / ".venv/bin").mkdir(parents=True)
        os.symlink(sys.executable, release / ".venv/bin/python3")
        orch = vps.Orchestrator(release, self.mutable / "runtime", (),
                                require_release_manifest=True)
        health = orch.health()
        self.assertEqual(health["release_git_sha"], sha)
        self.assertEqual(health["effective_config_fingerprint"], fingerprint)
        manifest["git_commit_sha"] = "c" * 40
        (release / vps.RELEASE_MANIFEST_FILENAME).write_text(json.dumps(manifest))
        with self.assertRaises(vps.ContractError):
            vps.Orchestrator(release, self.mutable / "bad", (), require_release_manifest=True)

    def test_shell_python_resolves_release_venv_despite_hostile_path(self):
        release = self.mutable / "release"
        (release / "config").mkdir(parents=True)
        (release / "config/production-vps.env").write_bytes((ROOT / "config/production-vps.env").read_bytes())
        fake_bin = release / ".venv/bin"
        fake_bin.mkdir(parents=True)
        os.symlink(sys.executable, fake_bin / "python3")
        orch = vps.Orchestrator(release, self.mutable / "runtime", ())
        with mock.patch.dict(os.environ, {"PATH": "/hostile/bin:/usr/bin:/bin"}):
            env = orch.child_env()
        self.assertEqual(env["PATH"].split(os.pathsep)[0], str(fake_bin))
        resolved = subprocess.run(["bash", "-c", "command -v python3"], env=env,
                                  text=True, capture_output=True, check=True).stdout.strip()
        self.assertEqual(Path(resolved), fake_bin / "python3")

    def test_child_environment_replaces_bootstrap_path_with_exact_release(self):
        orch = self.orch()
        with mock.patch.dict(os.environ, {"PYTHONPATH": "/hostile/bootstrap"}):
            env = orch.child_env()
        self.assertEqual(env["PYTHONPATH"], str(ROOT / "r5_bootstrap"))

    def test_direct_and_shell_python_children_auto_load_exact_release_bootstrap(self):
        orch = self.orch()
        env = orch.child_env()
        env.update(BOTA_R5_SHADOW="1", BOTA_REQUIRE_R5_SHADOW="1")
        assertion = (
            "import os,pathlib,sys;"
            "assert os.environ['BOTA_R5_BOOTSTRAP_ACTIVE']=='1';"
            f"assert pathlib.Path(sys.modules['sitecustomize'].__file__).resolve()==pathlib.Path({str(ROOT / 'r5_bootstrap/sitecustomize.py')!r}).resolve()"
        )
        direct = subprocess.run([sys.executable, "-c", assertion], env=env, cwd=ROOT,
                                text=True, capture_output=True, timeout=10)
        self.assertEqual(direct.returncode, 0, direct.stderr)
        shell = subprocess.run(["bash", "-c", f"python3 -c {shlex.quote(assertion)}"],
                               env=env, cwd=ROOT, text=True, capture_output=True, timeout=10)
        self.assertEqual(shell.returncode, 0, shell.stderr)

    def test_orchestrator_main_fails_closed_for_unproven_r5_bootstrap(self):
        with mock.patch.dict(os.environ, {"BOTA_R5_SHADOW": "1",
                                          "BOTA_R5_BOOTSTRAP_ACTIVE": "1"}, clear=False):
            with mock.patch.object(vps.sys, "modules", dict(vps.sys.modules)):
                vps.sys.modules.pop("sitecustomize", None)
                with mock.patch("sys.stderr"):
                    self.assertEqual(vps.main([]), 78)

    def test_orchestrator_main_fails_closed_when_r5_required_but_inactive(self):
        for shadow in (None, "0"):
            with self.subTest(shadow=shadow):
                environment = {"BOTA_REQUIRE_R5_SHADOW": "1"}
                if shadow is not None:
                    environment["BOTA_R5_SHADOW"] = shadow
                with mock.patch.dict(os.environ, environment, clear=True):
                    with mock.patch("sys.stderr"):
                        self.assertEqual(vps.main([]), 78)

    def test_orchestrator_r5_guard_is_inert_without_r5_flags(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            vps.require_r5_bootstrap(ROOT)

    def test_updater_environment_is_exact_and_cannot_leak(self):
        jobs = {job.name: job for job in vps.production_jobs()}
        hostile = {"TIMEFRAMES": "HOSTILE", "FETCH_RETRIES": "999"}
        with mock.patch.dict(os.environ, hostile):
            orch = self.orch()
            updater = orch.child_env(jobs["updater"])
            watcher = orch.child_env(jobs["watcher"])
        self.assertEqual({key: updater[key] for key in vps.UPDATER_ENV}, vps.UPDATER_ENV)
        self.assertEqual(watcher["TIMEFRAMES"], "M15")
        for key in set(vps.UPDATER_ENV) - set(vps.POLICY_KEYS):
            self.assertNotEqual(watcher.get(key), vps.UPDATER_ENV[key])

    def test_updater_stages_have_separate_deadlines_and_failure_evidence(self):
        marker = self.mutable / "d1"
        failed = vps.Job("updater", ((sys.executable, "-c", "raise SystemExit(7)"),
                                     (sys.executable, "-c", f"open({str(marker)!r},'w').write('x')")),
                         vps.UPDATER_MINUTES, 0.1, (0.1, 2.0),
                         stage_names=("indicators_updater", "d1_sync"))
        result = self.launch_wait(self.orch(), failed)
        self.assertFalse(marker.exists())
        self.assertEqual(result["failed_stage"], "indicators_updater")
        self.assertEqual(result["stage_results"][0]["status"], "FAILED")

        timed_marker = self.mutable / "d1_after_timeout"
        timed = vps.Job("updater", ((sys.executable, "-c", "import time; time.sleep(.2)"),
                                    (sys.executable, "-c",
                                     f"open({str(timed_marker)!r},'w').write('x')")),
                        vps.UPDATER_MINUTES, 0.05, (0.05, 1.0),
                        stage_names=("indicators_updater", "d1_sync"))
        result = self.launch_wait(self.orch(grace=0.01), timed)
        self.assertEqual((result["status"], result["failed_stage"]),
                         ("TIMED_OUT", "indicators_updater"))
        self.assertFalse(timed_marker.exists())

        independent = vps.Job("updater2", (("stage-one",), ("stage-two",)),
                              vps.UPDATER_MINUTES, 0.1, (0.1, 0.2))
        seen_timeouts = []

        class PopenSpy:
            next_pid = 50000

            def __init__(self, *args, **kwargs):
                self.stdout = io.BytesIO()
                self.returncode = None
                self.pid = PopenSpy.next_pid
                PopenSpy.next_pid += 1

            def wait(self, timeout=None):
                seen_timeouts.append(timeout)
                self.returncode = 0
                return 0

            def poll(self):
                return self.returncode

        with mock.patch.object(vps.subprocess, "Popen", PopenSpy):
            result = self.launch_wait(self.orch(), independent)

        self.assertEqual(result["status"], "PASS")
        self.assertEqual(seen_timeouts, [0.1, 0.2])
        self.assertEqual([stage["deadline_seconds"] for stage in result["stage_results"]],
                         [0.1, 0.2])

        d1_failure = vps.Job("updater3", ((sys.executable, "-c", "pass"),
                                          (sys.executable, "-c", "raise SystemExit(9)")),
                             vps.UPDATER_MINUTES, 1, (1, 1),
                             stage_names=("indicators_updater", "d1_sync"))
        result = self.launch_wait(self.orch(), d1_failure)
        self.assertEqual((result["status"], result["failed_stage"]), ("FAILED", "d1_sync"))

    def test_job_environment_contract_rejects_generic_policy_override(self):
        with self.assertRaises(vps.ContractError):
            vps.Job("watcher", (("true",),), vps.EVERY_MINUTE, 1,
                    env_overrides=(("TIMEFRAMES", "H1"),))

    def test_terminal_staleness_uses_full_daily_and_weekly_cadence(self):
        daily = vps.Job("daily", (("true",),), vps.DAILY_0506, 60)
        sunday = vps.Job("weekly", (("true",),), vps.SUNDAY_0100, 60)
        daily_record = {"status": "PASS", "scheduled_for_utc": "2026-08-24T05:06:00Z"}
        weekly_record = {"status": "PASS", "scheduled_for_utc": "2026-08-23T01:00:00Z"}
        self.assertFalse(vps.Orchestrator._is_stale(
            daily, daily_record, datetime(2026, 8, 24, 23, tzinfo=timezone.utc)))
        self.assertFalse(vps.Orchestrator._is_stale(
            daily, daily_record, datetime(2026, 8, 25, 5, 7, tzinfo=timezone.utc)))
        self.assertTrue(vps.Orchestrator._is_stale(
            daily, daily_record, datetime(2026, 8, 25, 5, 8, 1, tzinfo=timezone.utc)))
        self.assertFalse(vps.Orchestrator._is_stale(
            sunday, weekly_record, datetime(2026, 8, 29, 23, tzinfo=timezone.utc)))
        self.assertFalse(vps.Orchestrator._is_stale(
            sunday, weekly_record, datetime(2026, 8, 30, 1, 2, tzinfo=timezone.utc)))
        self.assertTrue(vps.Orchestrator._is_stale(
            sunday, weekly_record, datetime(2026, 8, 30, 1, 2, 1, tzinfo=timezone.utc)))

    def test_frequent_cadences_stale_after_next_boundary_and_allowance(self):
        base = datetime(2026, 8, 23, 12, 0, tzinfo=timezone.utc)
        for cadence in (vps.EVERY_MINUTE, vps.EVERY_5_MINUTES, vps.EVERY_15_MINUTES,
                        vps.EVERY_30_MINUTES, vps.UPDATER_MINUTES):
            job = vps.Job("job", (("true",),), cadence, 60)
            record = {"status": "PASS", "scheduled_for_utc": base.isoformat()}
            boundary = cadence.next_after(base)
            self.assertFalse(vps.Orchestrator._is_stale(job, record, boundary + timedelta(seconds=120)))
            self.assertTrue(vps.Orchestrator._is_stale(job, record, boundary + timedelta(seconds=121)))

    def test_production_job_table_is_gated_and_has_no_control_authority(self):
        jobs = {job.name: job for job in vps.production_jobs()}
        self.assertEqual(set(jobs), {"updater", "watcher", "shadow", "closer", "heartbeat",
                                     "profitlab_delivery", "runtime_health_push", "market_pulse",
                                     "alerts_to_trades", "pause_guard", "autostatus",
                                     "signal_accuracy", "daily_summary_server_gate"})
        self.assertTrue(jobs["watcher"].commands[0][1].endswith("watcher_gated_cycle.sh"))
        self.assertEqual({name: jobs[name].deadline_seconds for name in
                          ("updater", "watcher", "shadow", "profitlab_delivery", "market_pulse")},
                         {"updater": 600, "watcher": 720, "shadow": 720,
                          "profitlab_delivery": 45, "market_pulse": 25})
        self.assertEqual(jobs["updater"].stage_deadlines, (600, 3600))
        self.assertEqual(jobs["updater"].stage_names, ("indicators_updater", "d1_sync"))
        rendered = json.dumps([[*command] for job in jobs.values() for command in job.commands]).lower()
        for forbidden in ("runsv", "runit", "crond", "watchdog"):
            self.assertNotIn(forbidden, rendered)
        self.assertTrue(jobs["alerts_to_trades"].commands[0][1].endswith("alerts_to_trades.py"))
        self.assertTrue(jobs["pause_guard"].commands[0][1].endswith("pause_guard.py"))
        self.assertTrue(jobs["autostatus"].commands[0][1].endswith("autostatus.sh"))
        self.assertTrue(jobs["signal_accuracy"].commands[0][1].endswith("signal_accuracy.py"))
        self.assertTrue(jobs["daily_summary_server_gate"].commands[0][1].endswith(
            "daily_summary_server_gate.sh"))
        gate = (ROOT / "tools" / "daily_summary_server_gate.sh").read_text(encoding="utf-8")
        self.assertIn('TARGET_HOUR_UTC="${DAILY_SUMMARY_TARGET_HOUR_UTC:-20}"', gate)
        self.assertIn('SENT_FILE="${STATE_DIR}/daily_summary_sent_${server_date}.ok"', gate)


if __name__ == "__main__":
    unittest.main()
