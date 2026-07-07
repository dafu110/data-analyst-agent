from __future__ import annotations

import argparse
import sys
from pathlib import Path

from data_analyst_agent.agent import DataAnalystAgent


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the Data Analyst Agent on a CSV file.")
    parser.add_argument("dataset", help="Path to a CSV dataset.")
    parser.add_argument("--goal", default="Profile the dataset and find useful patterns.", help="Analysis goal.")
    parser.add_argument("--output", help="Optional Markdown report path.")
    return parser


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    args = build_parser().parse_args()
    result = DataAnalystAgent().analyze_csv(args.dataset, args.goal)

    if args.output:
        output_path = Path(args.output)
        output_path.write_text(result.report_markdown, encoding="utf-8")
        print(f"Report written to {output_path}")
    else:
        print(result.report_markdown)


if __name__ == "__main__":
    main()
