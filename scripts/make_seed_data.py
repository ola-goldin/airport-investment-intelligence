"""Deterministic generator for the bundled BTS T-100 seed dataset.

PROVENANCE NOTE (also surfaced via the API):
  The bundled seed is NOT live BTS data. It is a deterministic, real-world-
  calibrated dataset following the BTS T-100 (Domestic + International)
  market schema: passengers, seats, scheduled/performed departures, and
  long-haul (>= 3000 mi nonstop) shares per airport-year, 2019-2023.

  Magnitudes are calibrated to published airport statistics; values are
  approximate and intended to make the demo reproducible without network
  access. Replace via backend/app/data/bts.py to use authoritative BTS data.

Outputs:
  data/raw/bts_t100_seed.csv
  data/raw/ourairports/airports_seed.csv
"""
from __future__ import annotations

import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

YEARS = [2019, 2020, 2021, 2022, 2023]
RECOVERY_2020 = 0.35  # uniform COVID-year traffic factor

# iata: (name, city, state, pax2019_millions, pax_per_dep, seats_per_dep,
#        lf_offset, recovery2021, recovery2023, trend2022, trend2023,
#        long_haul_share, lat, lon)
AIRPORTS: dict[str, tuple] = {
    "ATL": ("Hartsfield-Jackson Atlanta International", "Atlanta", "GA", 110.5, 130, 168, +0.01, 0.78, 0.94, +0.03, +0.02, 0.04, 33.6, -84.4),
    "LAX": ("Los Angeles International", "Los Angeles", "CA", 88.1, 135, 172, 0.00, 0.55, 0.87, -0.01, +0.03, 0.15, 33.9, -118.4),
    "ORD": ("Chicago O'Hare International", "Chicago", "IL", 84.6, 125, 165, -0.01, 0.60, 0.92, +0.02, +0.02, 0.11, 42.0, -87.9),
    "DFW": ("Dallas/Fort Worth International", "Dallas-Fort Worth", "TX", 75.1, 132, 170, +0.02, 0.80, 1.00, +0.02, +0.01, 0.07, 32.9, -97.0),
    "DEN": ("Denver International", "Denver", "CO", 73.0, 128, 168, +0.01, 0.78, 1.07, +0.03, +0.02, 0.04, 39.9, -104.7),
    "JFK": ("John F. Kennedy International", "New York", "NY", 62.6, 190, 230, -0.02, 0.46, 0.93, 0.00, +0.02, 0.28, 40.6, -73.8),
    "SFO": ("San Francisco International", "San Francisco", "CA", 57.9, 145, 180, +0.02, 0.48, 0.87, +0.01, +0.03, 0.22, 37.6, -122.4),
    "SEA": ("Seattle-Tacoma International", "Seattle", "WA", 51.8, 138, 175, +0.01, 0.55, 0.95, +0.02, +0.02, 0.10, 47.5, -122.3),
    "LAS": ("Harry Reid International", "Las Vegas", "NV", 50.7, 150, 178, +0.01, 0.80, 1.06, +0.01, +0.01, 0.01, 36.1, -115.2),
    "CLT": ("Charlotte Douglas International", "Charlotte", "NC", 50.2, 120, 165, 0.00, 0.77, 0.99, +0.02, +0.01, 0.02, 35.2, -80.9),
    "PHX": ("Phoenix Sky Harbor International", "Phoenix", "AZ", 49.3, 142, 175, +0.01, 0.78, 1.04, +0.02, +0.01, 0.02, 33.4, -112.0),
    "MIA": ("Miami International", "Miami", "FL", 45.9, 160, 200, +0.02, 0.74, 1.05, +0.03, +0.02, 0.16, 25.8, -80.3),
    "IAH": ("George Bush Intercontinental", "Houston", "TX", 44.9, 140, 178, 0.00, 0.65, 0.98, +0.01, +0.01, 0.09, 30.0, -95.3),
    "EWR": ("Newark Liberty International", "Newark", "NJ", 46.3, 155, 195, -0.01, 0.59, 0.96, +0.01, +0.02, 0.17, 40.7, -74.2),
    "BOS": ("Edward Lawrence Logan International", "Boston", "MA", 40.8, 132, 172, +0.02, 0.62, 1.05, +0.02, +0.03, 0.05, 42.4, -71.0),
    "MSP": ("Minneapolis-St. Paul International", "Minneapolis", "MN", 38.8, 128, 168, 0.00, 0.68, 0.95, +0.01, +0.01, 0.03, 44.9, -93.2),
    "PHL": ("Philadelphia International", "Philadelphia", "PA", 33.0, 135, 175, 0.00, 0.65, 0.94, +0.01, +0.01, 0.05, 39.9, -75.2),
    "IAD": ("Washington Dulles International", "Washington", "DC", 24.9, 150, 195, +0.01, 0.45, 0.94, +0.01, +0.02, 0.30, 39.0, -77.5),
    "SAN": ("San Diego International", "San Diego", "CA", 25.2, 105, 160, +0.01, 0.66, 0.97, +0.02, +0.02, 0.01, 32.7, -117.2),
    "HNL": ("Daniel K. Inouye International", "Honolulu", "HI", 20.6, 150, 195, -0.01, 0.48, 0.85, 0.00, +0.01, 0.28, 21.3, -157.9),
    "ANC": ("Ted Stevens Anchorage International", "Anchorage", "AK", 5.5, 95, 150, 0.00, 0.62, 0.96, +0.02, +0.02, 0.08, 61.2, -150.0),
    "OAK": ("Oakland International", "Oakland", "CA", 13.3, 90, 165, 0.00, 0.47, 0.86, +0.01, +0.01, 0.00, 37.7, -122.2),
    "SJC": ("Norman Y. Mineta San Jose International", "San Jose", "CA", 11.4, 115, 168, 0.00, 0.46, 0.85, 0.00, +0.01, 0.02, 37.4, -121.9),
    "SNA": ("John Wayne Airport", "Santa Ana", "CA", 10.4, 68, 150, +0.02, 0.58, 1.06, +0.02, +0.02, 0.01, 33.7, -117.9),
    "BUR": ("Hollywood Burbank Airport", "Burbank", "CA", 4.3, 70, 150, 0.00, 0.53, 0.95, +0.01, +0.01, 0.00, 34.2, -118.4),
    "BDL": ("Bradley International", "Hartford", "CT", 6.5, 75, 155, +0.01, 0.62, 0.98, +0.02, +0.02, 0.01, 41.9, -72.7),
    "PVD": ("Rhode Island T. F. Green International", "Providence", "RI", 4.1, 70, 150, 0.00, 0.62, 0.98, +0.01, +0.01, 0.01, 41.7, -71.4),
    "MHT": ("Manchester-Boston Regional", "Manchester", "NH", 2.6, 65, 145, 0.00, 0.60, 1.00, +0.02, +0.01, 0.00, 42.9, -71.4),
    "PWM": ("Portland International Jetport", "Portland", "ME", 2.2, 60, 140, +0.01, 0.62, 1.05, +0.02, +0.02, 0.00, 43.6, -70.3),
}


def load_factor(iata: str, year: int) -> float:
    (name, city, state, pax_m, ppd, spd, lf_off, r21, r23, t22, t23, lh, lat, lon) = AIRPORTS[iata]
    base = 0.815 + lf_off - (0.03 if pax_m < 15.0 else 0.0)
    curve = {
        2019: 0.0,
        2020: -0.27,
        2021: -0.10,
        2022: t22 * 0.5,
        2023: t22 * 0.5 + t23 * 0.5 + 0.005,
    }[year]
    return min(0.92, max(0.45, base + curve))


def rows():
    t100_rows = []
    for iata, spec in AIRPORTS.items():
        (name, city, state, pax_m, ppd, spd, lf_off, r21, r23, t22, t23, lh, lat, lon) = spec
        pax_2019 = pax_m * 1e6
        recovery = {2019: 1.0, 2020: RECOVERY_2020, 2021: r21, 2023: r23}
        recovery[2022] = 0.5 * (r21 + r23)
        for year in YEARS:
            pax = round(pax_2019 * recovery[year])
            lf = load_factor(iata, year)
            seats = round(pax / lf)
            dep_performed = round(seats / spd)
            dep_scheduled = round(dep_performed * 1.02)
            lh_dep = round(dep_performed * lh)
            lh_seats = round(seats * lh)
            t100_rows.append({
                "year": year,
                "airport_iata": iata,
                "passengers": pax,
                "seats": seats,
                "departures_scheduled": dep_scheduled,
                "departures_performed": dep_performed,
                "long_haul_departures": lh_dep,
                "long_haul_seats": lh_seats,
            })
    return t100_rows


def metadata_rows():
    out = []
    for iata, spec in AIRPORTS.items():
        (name, city, state, pax_m, ppd, spd, lf_off, r21, r23, t22, t23, lh, lat, lon) = spec
        out.append({
            "iata_code": iata,
            "name": name,
            "city": city,
            "state": state,
            "latitude_deg": lat,
            "longitude_deg": lon,
        })
    return out


def main() -> None:
    t100_path = ROOT / "data" / "raw" / "bts_t100_seed.csv"
    t100_path.parent.mkdir(parents=True, exist_ok=True)
    t100_rows = rows()
    with t100_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(t100_rows[0].keys()))
        w.writeheader()
        w.writerows(t100_rows)

    meta_path = ROOT / "data" / "raw" / "ourairports" / "airports_seed.csv"
    meta_path.parent.mkdir(parents=True, exist_ok=True)
    meta = metadata_rows()
    with meta_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(meta[0].keys()))
        w.writeheader()
        w.writerows(meta)

    print(f"wrote {t100_path} ({len(t100_rows)} rows)")
    print(f"wrote {meta_path} ({len(meta)} rows)")


if __name__ == "__main__":
    main()
