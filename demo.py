#!/usr/bin/env python3
"""
Demo script for Airport Investment Intelligence Agent

This script demonstrates the core functionality of the airport investment analysis agent.
It shows how to use the deterministic scoring system to rank airports for investment potential.
"""

import sys

from agent import AirportInvestmentAgent
import json

# Windows legacy console code pages (e.g. cp1252) cannot encode emoji and
# box-drawing characters; force UTF-8 output so the demo never crashes.
stdout = getattr(sys.stdout, "reconfigure", None)
if stdout is not None:
    stdout(encoding="utf-8", errors="replace")

def main():
    """Run the Airport Investment Intelligence Agent demo."""
    print("=" * 70)
    print("AIRPORT INVESTMENT INTELLIGENCE AGENT - DEMONSTRATION")
    print("=" * 70)
    print()
    print("This agent identifies profitable airport investment opportunities by analyzing")
    print("flight capacity, passenger data, and congestion levels across US airports.")
    print()
    print("The system uses a deterministic scoring framework:")
    print("  Score = (0.4 × Passenger Growth) + (0.3 × Long-Haul Ratio) + (0.3 × Cargo Volume)")
    print()
    
    # Initialize the agent
    print("Initializing Airport Investment Agent...")
    agent = AirportInvestmentAgent()
    
    # Run the complete analysis
    print("\nRunning airport investment analysis...")
    results = agent.analyze()
    
    # Display summary
    print("\n" + "=" * 70)
    print("ANALYSIS COMPLETE")
    print("=" * 70)
    
    print("\nKey Results:")
    print(f"• Analysis Date: {results['analysis_date']}")
    print(f"• Airports Analyzed: {len(results['rankings'])}")
    print(f"• Database Path: {agent.db_path}")
    
    # Show top 3 airports
    print("\nTop 3 Ranked Airports:")
    print("-" * 50)
    for i, ranking in enumerate(results['rankings'][:3], 1):
        print(f"{i}. {ranking['iata_code']} - {ranking['name']}")
        print(f"   Investment Score: {ranking['score']:.3f}")
        print(f"   Ranking Position: {ranking['ranking_position']}")
    
    # Show example comparison
    if len(results['rankings']) >= 2:
        print(f"\nExample Comparison:")
        print("-" * 50)
        airport1 = next(a for a in results['airports'] if a['iata_code'] == results['rankings'][0]['iata_code'])
        airport2 = next(a for a in results['airports'] if a['iata_code'] == results['rankings'][1]['iata_code'])
        
        print(f"{airport1['iata_code']} vs {airport2['iata_code']}")
        print(f"Score Difference: {abs(airport1['score'] - airport2['score']):.3f}")
        
        if airport1['score'] > airport2['score']:
            print(f"Winner: {airport1['iata_code']} ({airport1['name']})")
        else:
            print(f"Winner: {airport2['iata_code']} ({airport2['name']})")
    
    # Export results
    print(f"\nExporting results to: airport_investment_results.json")
    agent.export_results(results)
    
    print("\n" + "=" * 70)
    print("DEMONSTRATION COMPLETE")
    print("=" * 70)
    
    print("\nNext Steps:")
    print("• Integrate with FAA Aeronautical Data APIs")
    print("• Add OpenSky Network data collection")
    print("• Build chat interface for natural language queries")
    print("• Implement machine learning for prediction capabilities")
    print("• Create dashboard for visualization")
    
    print("\nKey Features Implemented:")
    print("✅ Deterministic scoring algorithm")
    print("✅ Multi-source data integration framework")
    print("✅ SQLite database for persistent storage")
    print("✅ Airport ranking and comparison capabilities")
    print("✅ Export functionality for further analysis")
    print("✅ Professional documentation and setup guides")
    
    print("\nProject Structure:")
    print("  agent.py                    # Core agent implementation")
    print("  app.py                      # Main application entry point")
    print("  demo.py                     # This demonstration script")
    print("  data/                       # SQLite database storage")
    print("  requirements.txt            # Python dependencies")
    print("  INSTALL.md                  # Installation guide")
    print("  README.md                   # Project documentation")
    
    print("\nFor more information, visit the project documentation.")
    print("=" * 70)

if __name__ == "__main__":
    main()