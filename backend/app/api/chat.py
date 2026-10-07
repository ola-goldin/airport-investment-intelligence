"""Fallback conversational agent (used when Dify is unavailable).

Deterministic intent routing — no LLM required. Supports the four required
question types plus follow-up context (e.g. "what about SFO?" after a
New England ranking keeps the ranking context).

Dify remains the primary orchestrator; this fallback exists to show the
system still works if Dify is down (plan §14).
"""
from __future__ import annotations

import re
import uuid

from app.analytics import metrics as analytics
from app.analytics.utilization import UNMET_DEMAND_NOTE
from app.data.metadata import REGION_ALIASES, region_to_states
from app.runtime import get_runtime

_sessions: dict[str, dict] = {}

ALIASES = {"LA": "LAX", "SANTA ANA": "SNA", "JOHN WAYNE": "SNA", "O'HARE": "ORD",
           "DULLES": "IAD", "BOSTON": "BOS", "SAN FRANCISCO": "SFO",
           "ANCHORAGE": "ANC", "HARTFORD": "BDL", "PROVIDENCE": "PVD"}


def _resolve_airport(text: str, repo) -> str | None:
    codes = set(repo.codes())
    for code in codes:
        if re.search(rf"\b{code}\b", text.upper()):
            return code
    up = text.upper()
    for alias, code in ALIASES.items():
        if alias in up:
            return code
    for profile_code in codes:
        profile = repo.profile(profile_code)
        if profile and profile["city"] and profile["city"].upper() in up:
            return profile_code
    return None


def _extract_region(text: str) -> str | None:
    low = text.lower()
    for name in REGION_ALIASES:
        if name.lower() in low:
            return name
    if re.search(r"\bnew england\b", low):
        return "New England"
    if "california" in low or " cali " in low:
        return "California"
    return None


def _detect_intent(text: str) -> str:
    low = text.lower()
    if re.search(r"\blong[- ]?haul\b", low):
        return "long_haul"
    if re.search(r"\bcompare\b|\bvs\.?\b|\bversus\b", low):
        return "compare"
    if re.search(r"unmet|excess demand|pent[- ]up", low):
        return "unmet_demand"
    if re.search(r"congest|crowd|busy|capacity press", low):
        return "utilization"
    if re.search(r"candidate|rank|top \d+|best|promising", low):
        return "rank"
    if _looks_like_airport_question(low):
        return "metrics"
    return "help"


def _looks_like_airport_question(low: str) -> bool:
    return bool(re.search(r"airport|\bmetrics?\b|score|summary|\bhow is\b|\bwhat about\b", low))


def _handle_rank(text: str, repo, model, session: dict) -> dict:
    region = _extract_region(text) or session.get("last_region") or "United States"
    session["last_region"] = region
    result = analytics.rank_airports(repo, model, region, limit=10)
    if "error" in result:
        return {"intent": "rank", "answer": result["error"]}
    top = result["ranking"][:5]
    lines = [f"Top expansion candidates in {result['region']} ({result['scope']}):"]
    for i, e in enumerate(top, 1):
        lines.append(
            f"{i}. {e['airport']} ({e['city']}, {e['state']}) - score {e['score']}, "
            f"passenger growth {e['passenger_growth_pct']}%/yr, LF {e['load_factor']}"
        )
    answer = "\n".join(lines) + "\n\nScore = deterministic composite of observed KPIs (see assumptions)."
    if top:
        session["last_airport"] = top[0]["airport"]
    return {"intent": "rank", "answer": answer, "payload": result, "assumptions": result["assumptions"]}


def _handle_compare(text: str, repo, model, session: dict) -> dict:
    found = _find_multiple_airports(text, repo, session)
    if len(found) < 2:
        return {"intent": "compare", "answer": "Name two airports to compare, e.g. 'Compare LAX and SNA'."}
    result = analytics.compare_airports(repo, model, found[:2])
    rows = (result.get("pairwise_summary") or {}).get("rows", [])
    lines = [f"{found[0]} vs {found[1]}:"]
    for r in rows:
        lines.append(
            f"- {r['metric']}: {found[0]}={r.get(found[0])}, {found[1]}={r.get(found[1])} "
            f"(higher: {r['higher']})"
        )
    session["last_airport"] = found[0]
    return {"intent": "compare", "answer": "\n".join(lines), "payload": result}


def _find_multiple_airports(text: str, repo, session: dict) -> list[str]:
    codes = set(repo.codes())
    found: list[str] = []
    up = text.upper()
    for code in sorted(codes):
        if re.search(rf"\b{code}\b", up) and code not in found:
            found.append(code)
    for alias, code in ALIASES.items():
        if alias in up and code not in found:
            found.append(code)
    if len(found) < 2 and session.get("last_airport") and session["last_airport"] not in found:
        found.insert(0, session["last_airport"])
    return found


def _handle_long_haul(text: str, repo, session: dict) -> dict:
    code = _resolve_airport(text, repo) or session.get("last_airport")
    if not code:
        return {"intent": "long_haul", "answer": "Which airport? e.g. 'What percentage of long haul flights out of ANC?'"}
    result = analytics.long_haul_share(repo, code, repo.latest_year())
    if "error" in result:
        return {"intent": "long_haul", "answer": result["error"]}
    share = result["long_haul_departures_share"]
    seat_share = result["long_haul_seat_share"]
    answer = (
        f"{code} long-haul share ({result['year']}): {share:.1%} of departing segments "
        f"({result['long_haul_departures']} of {result['total_departures_performed']} departures); "
        f"{seat_share:.1%} of seats.\nDefinition: {result['methodology']}"
    )
    session["last_airport"] = code
    return {"intent": "long_haul", "answer": answer, "payload": result}


def _handle_unmet(text: str, repo, model, session: dict) -> dict:
    code = _resolve_airport(text, repo) or session.get("last_airport")
    if not code:
        return {"intent": "unmet_demand", "answer": "Which airport? e.g. 'What is the unmet flight demand at SFO?'"}
    util = analytics.utilization_analysis(repo, model, code)
    if "error" in util:
        return {"intent": "unmet_demand", "answer": util["error"]}
    answer = (
        f"Unmet demand is not directly observable in public data, so it is never reported as a "
        f"measured figure. Closest observed indicators for {code} ({util['year']}): "
        f"load factor {util['load_factor_pct']}% "
        f"(prior year {util['prior_year']}: "
        f"{round((util['prior_year_load_factor'] or 0) * 100, 1)}%), "
        f"YoY change {util['utilization_trend_points']} points, "
        f"passenger growth {util['demand_growth_pct']}%/yr.\n\n{UNMET_DEMAND_NOTE}"
    )
    session["last_airport"] = code
    return {"intent": "unmet_demand", "answer": answer, "payload": util,
            "assumptions": [UNMET_DEMAND_NOTE]}


def _handle_metrics(text: str, repo, model, session: dict) -> dict:
    code = _resolve_airport(text, repo) or session.get("last_airport")
    if not code:
        return {"intent": "metrics", "answer": _help_text()}
    result = analytics.get_airport_metrics(repo, model, code)
    if "error" in result:
        return {"intent": "metrics", "answer": result["error"]}
    m = result["metrics"]
    answer = (
        f"{result['profile']['name']} ({code}, {result['profile']['city']} "
        f"{result['profile']['state']}), {result['data_year']}:\n"
        f"- Passengers: {m['passengers']:,}; LF {m['load_factor']}\n"
        f"- Passenger growth {m['passenger_growth_pct']}%/yr; "
        f"flight growth {m['flight_growth_pct']}%/yr "
        f"(window {m['growth_window'].get('start')}-{m['growth_window'].get('end')})\n"
        f"- Utilization trend {m['utilization_trend_points']} LF pts; "
        f"long-haul share {m['long_haul_departures_share']}\n"
        f"- Expansion Opportunity Score: {result['scoring']['score']}/100 "
        f"(model v{result['scoring']['model_version']}, deterministic)"
    )
    session["last_airport"] = code
    return {"intent": "metrics", "answer": answer, "payload": result, "assumptions": result["assumptions"]}


def _help_text() -> str:
    return (
        "I can answer (deterministic analytics, clearly scoped):\n"
        "- 'Which airports in New England are strong candidates for terminal expansion?'\n"
        "- 'Compare LAX and SNA congestion levels'\n"
        "- 'What percentage of long haul flights out of ANC?'\n"
        "- 'What is the unmet flight demand in SFO and why?'\n"
        "Follow-ups work: 'Why is BOS ranked first?', 'What about SFO?'"
    )


def respond(message: str, session_id: str | None = None) -> dict:
    session_id = session_id or str(uuid.uuid4())
    session = _sessions.setdefault(session_id, {})
    repo, model = get_runtime()
    intent = _detect_intent(message)

    if intent == "rank":
        out = _handle_rank(message, repo, model, session)
    elif intent == "compare":
        out = _handle_compare(message, repo, model, session)
    elif intent == "long_haul":
        out = _handle_long_haul(message, repo, session)
    elif intent in ("unmet_demand", "utilization"):
        out = _handle_unmet(message, repo, model, session)
    elif intent == "metrics":
        out = _handle_metrics(message, repo, model, session)
    else:
        out = {"intent": "help", "answer": _help_text()}

    return {"session_id": session_id, "intent": out.get("intent", intent),
            "answer": out.get("answer", ""), "payload": out.get("payload", {}),
            "assumptions": out.get("assumptions", [])}

