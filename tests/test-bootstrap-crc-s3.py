"""Cenários sintéticos; não acessa clusters nem credenciais reais."""
import contextlib
import io
import json
import os
from pathlib import Path
import runpy
import subprocess
import unittest
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/bootstrap-crc-s3.py"


class BootstrapTest(unittest.TestCase):
    def execute(self, *, options=(), scenario="ok"):
        calls = []
        output = io.StringIO()
        marker = "CREDENCIAL-SINTETICA-NAO-EXIBIR"

        def fake(argv, **kwargs):
            calls.append((argv, kwargs))
            args = argv[argv.index("--context") + 2:] if "--context" in argv else argv[2:]
            code, stdout, stderr = 0, "", ""
            if args == ["config", "current-context"]:
                stdout = "keycloak-crc"
                if scenario == "no-context":
                    code, stderr = 1, marker
            elif args[:2] == ["config", "view"]:
                stdout = "https://corporativo.invalid:6443" if scenario == "other-cluster" else "https://api.crc.testing:6443"
                if scenario == "invalid-context":
                    code, stderr = 1, marker
            elif args == ["whoami"]:
                stdout = "openshift-admin"
                if scenario == "auth":
                    code, stderr = 1, marker
            elif args[:2] == ["get", "secret/minio-credentials"]:
                stdout = json.dumps({"data": {"root-user": "dXN1YXJpbw==", "root-password": marker}})
            elif args[:2] == ["get", "secret/netobserv-loki-s3"]:
                assert "--ignore-not-found" in args
                stdout = json.dumps({"data": {"access_key_id": "dXN1YXJpbw==", "access_key_secret": marker}})
                if scenario == "missing":
                    stdout = ""
                elif scenario == "forbidden":
                    code, stderr = 1, marker
                elif scenario == "mismatch":
                    stdout = json.dumps({"data": {"access_key_id": "diferente"}})
            elif args[:2] == ["get", "deployment/minio"]:
                stdout = json.dumps({"status": {"availableReplicas": 0 if scenario == "unavailable" else 1}})
            elif args[0] == "create":
                assert kwargs.get("input")
            elif args[0] == "get" and args[1].startswith("job/"):
                stdout = json.dumps({"status": {"succeeded": 1}})
            else:
                raise AssertionError(args)
            return subprocess.CompletedProcess(argv, code, stdout, stderr)

        with patch("sys.argv", [str(SCRIPT), *options]), patch("subprocess.run", side_effect=fake), patch.dict(os.environ, {"KUBECONFIG": "/tmp/config-sintetica"}), contextlib.redirect_stdout(output), contextlib.redirect_stderr(output):
            with self.assertRaises(SystemExit) as result:
                runpy.run_path(str(SCRIPT), run_name="__main__")
        self.assertNotIn(marker, output.getvalue())
        for argv, kwargs in calls:
            self.assertFalse(any(arg.startswith("--server") for arg in argv))
            self.assertNotIn("env", kwargs)  # herda KUBECONFIG do chamador
        return result.exception.code, calls, output.getvalue()

    def test_current_context_read_only(self):
        code, calls, _ = self.execute(options=("--check",))
        self.assertEqual(code, 0)
        self.assertFalse(any("create" in argv for argv, _ in calls))
        self.assertTrue(all("keycloak-crc" in argv for argv, _ in calls[1:]))

    def test_explicit_context(self):
        code, calls, _ = self.execute(options=("--check", "--context", "meu-crc"))
        self.assertEqual(code, 0)
        self.assertTrue(all("meu-crc" in argv for argv, _ in calls))
        self.assertFalse(any("current-context" in argv for argv, _ in calls))

    def test_reject_other_cluster_before_auth(self):
        code, calls, _ = self.execute(scenario="other-cluster")
        self.assertEqual(code, 1)
        self.assertEqual(len(calls), 2)

    def test_auth_failure_no_secret_read(self):
        code, calls, output = self.execute(scenario="auth")
        self.assertEqual(code, 1)
        self.assertEqual(len(calls), 3)
        self.assertIn("oc whoami", output)

    def test_missing_or_invalid_context(self):
        for scenario in ("no-context", "invalid-context"):
            with self.subTest(scenario=scenario):
                code, calls, _ = self.execute(scenario=scenario)
                self.assertEqual(code, 1)
                self.assertFalse(any("whoami" in argv for argv, _ in calls))

    def test_forbidden_never_creates(self):
        code, calls, _ = self.execute(scenario="forbidden")
        self.assertEqual(code, 1)
        self.assertFalse(any("create" in argv for argv, _ in calls))

    def test_mismatch_never_overwrites(self):
        code, calls, _ = self.execute(scenario="mismatch")
        self.assertEqual(code, 1)
        self.assertFalse(any("create" in argv for argv, _ in calls))

    def test_check_missing_secret_never_creates(self):
        code, calls, _ = self.execute(options=("--check",), scenario="missing")
        self.assertEqual(code, 1)
        self.assertFalse(any("create" in argv for argv, _ in calls))

    def test_check_unavailable_minio(self):
        code, _, _ = self.execute(options=("--check",), scenario="unavailable")
        self.assertEqual(code, 1)

    def test_bootstrap_missing_secret_and_bucket(self):
        code, calls, _ = self.execute(scenario="missing")
        self.assertEqual(code, 0)
        created = [json.loads(kwargs["input"]) for argv, kwargs in calls if "create" in argv]
        self.assertEqual([item["kind"] for item in created], ["Secret", "Job"])

    def test_existing_secret_only_creates_bucket_job(self):
        code, calls, _ = self.execute()
        self.assertEqual(code, 0)
        created = [json.loads(kwargs["input"]) for argv, kwargs in calls if "create" in argv]
        self.assertEqual([item["kind"] for item in created], ["Job"])


if __name__ == "__main__":
    unittest.main()
