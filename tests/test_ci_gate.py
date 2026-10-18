"""Exercise the real workflow gate against failed and incomplete job results."""
import json
import os
from pathlib import Path
import subprocess
import sys
import textwrap
import unittest


class WorkflowGateTest(unittest.TestCase):
    def run_gate(self, results):
        workflow = (Path(__file__).resolve().parents[1] / ".github/workflows/ci.yml").read_text()
        gate = workflow.split("      - name: Require all validation jobs\n", 1)[1]
        script = textwrap.dedent(gate.split("        run: |\n", 1)[1])
        return subprocess.run(
            [sys.executable, "-c", script],
            env={**os.environ, "RESULTS": json.dumps(results)},
            capture_output=True,
            text=True,
        )

    def test_all_checks_must_succeed(self):
        results = {name: {"result": "success"} for name in ("python", "security", "source", "training")}
        self.assertEqual(self.run_gate(results).returncode, 0)
        for name in results:
            for state in ("failure", "cancelled", "skipped"):
                with self.subTest(job=name, state=state):
                    changed = {**results, name: {"result": state}}
                    self.assertNotEqual(self.run_gate(changed).returncode, 0)

    def test_missing_or_unexpected_check_is_rejected(self):
        complete = {name: {"result": "success"} for name in ("python", "security", "source", "training")}
        self.assertNotEqual(self.run_gate({}).returncode, 0)
        self.assertNotEqual(self.run_gate({"python": complete["python"]}).returncode, 0)
        self.assertNotEqual(self.run_gate({**complete, "extra": {"result": "success"}}).returncode, 0)


if __name__ == "__main__":
    unittest.main()
