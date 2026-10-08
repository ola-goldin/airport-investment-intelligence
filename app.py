"""
Airport Investment Intelligence Agent

This is an AI-powered agent that identifies profitable airport investment opportunities by analyzing
flight capacity, passenger data, and congestion levels across US airports.

The system uses a deterministic scoring framework to rank airports objectively:
- Score = (0.4 * Passenger Growth) + (0.3 * Long-Haul Ratio) + (0.3 * Cargo Volume)

Integration Strategy:
- FAA Aeronautical Data: Real-time flight and airport information
- OpenSky Network: Aviation tracking data
- Wikipedia/Simple English Wikipedia: Airport metadata and background

AI Role:
- LLMs handle natural language query translation and conversational context
- Data retrieval and ranking are handled by deterministic Python logic
"""

import argparse
import json
import sys

from agent import AirportInvestmentAgent


def main(argv=None) -> int:
    """Run the airport investment analysis.

    Args:
        argv: Optional argument list (defaults to sys.argv[1:]).

    Returns:
        Process exit code (0 on success, 1 on failure).
    """
    parser = argparse.ArgumentParser(
        description="Airport Investment Intelligence Agent - deterministic airport "
        "investment ranking (Score = 0.4*Passenger Growth + 0.3*Long-Haul Ratio "
        "+ 0.3*Cargo Volume)."
    )
    parser.add_argument(
        "-o",
        "--output",
        default="airport_investment_results.json",
        help="Path for the exported JSON results (default: %(default)s)",
    )
    parser.add_argument(
        "--no-export",
        action="store_true",
        help="Skip writing the JSON results file",
    )
    args = parser.parse_args(argv)

    agent = AirportInvestmentAgent()
    results = agent.analyze()

    if not args.no_export:
        agent.export_results(results, args.output)

    # Machine-readable summary for downstream tooling / tests.
    summary = {
        "analysis_date": results["analysis_date"],
        "rankings": results["rankings"],
        "top_airport": results["rankings"][0]["iata_code"] if results["rankings"] else None,
    }
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())