"""
Airport Investment Intelligence Agent

AI-powered agent for airport investment analysis using deterministic scoring.
"""

import json
import os
import sqlite3
from datetime import datetime
from typing import Dict, List

class AirportInvestmentAgent:
    """Main agent for airport investment analysis."""
    
    def __init__(self):
        self.data_dir = "data"
        self.db_path = os.path.join(self.data_dir, "airport_metrics.db")
        self._init_database()
    
    def _init_database(self):
        """Initialize SQLite database."""
        os.makedirs(self.data_dir, exist_ok=True)
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS airports (
                iata_code TEXT PRIMARY KEY,
                name TEXT,
                passengers_2023 INTEGER,
                passengers_2022 INTEGER,
                cargo_volume_2023 INTEGER,
                score REAL,
                created_at TEXT
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def collect_data(self):
        """Collect sample airport data."""
        return [
            {
                "iata_code": "LAX",
                "name": "Los Angeles International Airport",
                "passengers_2023": 74049782,
                "passengers_2022": 67871634,
                "cargo_volume_2023": 500000
            },
            {
                "iata_code": "JFK",
                "name": "John F. Kennedy International Airport",
                "passengers_2023": 59043436,
                "passengers_2022": 53636673,
                "cargo_volume_2023": 750000
            },
            {
                "iata_code": "ORD",
                "name": "O'Hare International Airport",
                "passengers_2023": 62470072,
                "passengers_2022": 55650380,
                "cargo_volume_2023": 600000
            }
        ]
    
    def calculate_score(self, airport: Dict) -> float:
        """Calculate investment score."""
        passengers_2022 = airport.get("passengers_2022", 0)
        passengers_2023 = airport.get("passengers_2023", 0)
        
        if passengers_2022 > 0:
            passenger_growth = (passengers_2023 - passengers_2022) / passengers_2022
        else:
            passenger_growth = 0.0
        
        long_haul_ratio = 0.7
        cargo_volume = airport.get("cargo_volume_2023", 0)
        normalized_cargo = min(cargo_volume / 1000000, 1.0)
        
        score = (0.4 * passenger_growth + 
                 0.3 * long_haul_ratio + 
                 0.3 * normalized_cargo)
        
        return score
    
    def analyze(self) -> Dict:
        """Run complete analysis."""
        print("Airport Investment Intelligence Agent")
        print("=" * 50)
        
        airports = self.collect_data()
        
        scored_airports = []
        for airport in airports:
            score = self.calculate_score(airport)
            scored_airport = {
                **airport,
                "score": score,
                "passenger_growth_rate": (airport.get("passengers_2023", 0) - airport.get("passengers_2022", 0)) / airport.get("passengers_2022", 1),
                "long_haul_ratio": 0.7
            }
            scored_airports.append(scored_airport)
        
        scored_airports.sort(key=lambda x: x["score"], reverse=True)
        
        rankings = []
        for i, airport in enumerate(scored_airports, 1):
            rankings.append({
                "iata_code": airport["iata_code"],
                "name": airport["name"],
                "score": airport["score"],
                "ranking_position": i
            })
        
        self._display_results(rankings)
        
        if len(scored_airports) >= 2:
            print(f"\nExample Analysis: {scored_airports[0]['iata_code']} vs {scored_airports[1]['iata_code']}")
            print("-" * 50)
            
            airport1, airport2 = scored_airports[0], scored_airports[1]
            winner = airport1["iata_code"] if airport1["score"] > airport2["score"] else airport2["iata_code"]
            score_diff = abs(airport1["score"] - airport2["score"])
            
            print(f"Winner: {winner.upper()}")
            print(f"Score Difference: {score_diff:.3f}")
        
        return {
            "airports": scored_airports,
            "rankings": rankings,
            "analysis_date": datetime.now().isoformat()
        }
    
    def _display_results(self, rankings: List[Dict]):
        """Display results."""
        print("\nTop Ranked Airports:")
        print("-" * 60)
        
        for ranking in rankings:
            print(f"{ranking['ranking_position']}. {ranking['iata_code']} - {ranking['name']}")
            print(f"   Investment Score: {ranking['score']:.3f}")
            print()
    
    def export_results(self, results: Dict, output_file: str = "airport_investment_results.json"):
        """Export results."""
        with open(output_file, "w") as f:
            json.dump(results, f, indent=2)
        
        print(f"Results exported to: {output_file}")

if __name__ == "__main__":
    agent = AirportInvestmentAgent()
    results = agent.analyze()
    agent.export_results(results)
    
    print("\n" + "=" * 60)
    print("Airport Investment Analysis Complete!")
    print("The deterministic scoring system has ranked airports based on")
    print("passenger growth, long-haul ratios, and cargo volumes.")