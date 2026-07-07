from __future__ import annotations

import unittest
from pathlib import Path

from evals.run_evals import load_cases, run_case


ROOT = Path(__file__).resolve().parents[1]


class EvalRunnerTests(unittest.TestCase):
    def test_eval_cases_pass(self) -> None:
        cases = load_cases(ROOT / "evals" / "cases.json")
        results = [run_case(case) for case in cases]

        self.assertTrue(all(result["passed"] for result in results), results)


if __name__ == "__main__":
    unittest.main()
