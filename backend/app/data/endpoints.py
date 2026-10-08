"""External data-source endpoints (documentation + env wiring).

All public source URLs are configurable via environment variables so a
mirror or an updated endpoint can be swapped in without touching code.
Every variable ships a safe default here; .env.example documents them for
local overrides. Changing a URL never changes the analytics schema —
downloads are only ever used to refresh the authoritative raw inputs.
"""


def _env(name: str, default: str) -> str:
    """Read an env var, falling back to the documented default."""
    import os

    return os.getenv(name, default)


BTS_BASE_URL = _env(
    "BTS_BASE_URL",
    "https://www.transtats.bts.gov/DownLoad_Table.asp",
)
BTS_T100_QUERY = _env(
    "BTS_T100_QUERY",
    "?Table_ID=311&Year={year}&AllVars=1&Zype=csv",
)
FAA_ENPLANEMENTS_URL = _env(
    "FAA_ENPLANEMENTS_URL",
    "https://www.faa.gov/airports/planning_capacity/"
    "passenger_allcargo_stats/passenger/media/cy23-all-enplanements.xlsx",
)
OURAIRPORTS_URL = _env(
    "OURAIRPORTS_URL",
    "https://davidmegginson.github.io/ourairports-data/airports.csv",
)