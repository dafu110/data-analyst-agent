from __future__ import annotations

import unittest
from pathlib import Path

from data_analyst_agent.guardrails import GuardrailPolicy
from data_analyst_agent.plan_validator import PlanValidationError, plan_from_dict
from data_analyst_agent.profiler import load_csv, profile_dataframe


ROOT = Path(__file__).resolve().parents[1]


class PlanValidatorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.policy = GuardrailPolicy()
        df = load_csv(ROOT / "examples" / "sales.csv")
        self.profile = profile_dataframe(df, "sales.csv", self.policy)

    def test_accepts_valid_structured_plan(self) -> None:
        plan = plan_from_dict(
            {
                "user_goal": "Find revenue patterns",
                "steps": [
                    {
                        "id": "revenue-total",
                        "title": "Revenue total",
                        "tool": "sql",
                        "objective": "Calculate total revenue.",
                        "query": "select sum(revenue) as total_revenue from data",
                    }
                ],
            },
            self.profile,
            self.policy,
        )

        self.assertEqual(plan.steps[0].tool, "sql")

    def test_rejects_unsafe_plan(self) -> None:
        with self.assertRaises(PlanValidationError):
            plan_from_dict(
                {
                    "user_goal": "Read files",
                    "steps": [
                        {
                            "id": "unsafe-code",
                            "title": "Unsafe",
                            "tool": "python",
                            "objective": "Try file access.",
                            "code": "result = open('secret.txt').read()",
                        }
                    ],
                },
                self.profile,
                self.policy,
            )


if __name__ == "__main__":
    unittest.main()
