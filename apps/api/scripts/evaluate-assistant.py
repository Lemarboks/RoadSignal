"""Run frozen assistant smoke cases. Default is offline; --live uses configured models.

From apps/api: python scripts/evaluate-assistant.py [--live]
The suite never writes reports, route scores, traces containing content, or audio.
"""

import argparse
import asyncio
import json
import sys
from copy import deepcopy
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.ai import service
from app.ai.schemas import IncidentAnalysisRequest
from app.config import settings


async def evaluate(live: bool) -> int:
    if not live:
        settings.ai_enabled = False
        settings.embedding_base_url = ""
        settings.reranker_base_url = ""
    fixtures = json.loads(Path(service.__file__).with_name("evaluation-cases.json").read_text(encoding="utf-8"))
    results = []
    for case in fixtures["incident_cases"]:
        result = await service.analyse_incident(IncidentAnalysisRequest(text=case["text"]), [])
        correct = result.draft.incident_type == case["expected_type"]
        preserved = result.draft.description == case["text"] and result.requires_review
        results.append({"case": case["id"], "passed": correct and preserved, "mode": result.mode})
    route = deepcopy(fixtures["route_case"])
    result = await service.explain_route(route)
    supported = {item.id for item in result.evidence} <= {item.id for item in service.route_evidence(route)}
    results.append({"case": "immutable-route-evidence", "passed": supported and route == fixtures["route_case"] and result.score_unchanged, "mode": result.mode})
    models_used = all(item["mode"] == "model" for item in results)
    passed = all(item["passed"] for item in results) and (models_used if live else True)
    print(json.dumps({"fixture_version": fixtures["version"], "scope": fixtures["description"], "live_requested": live, "models_used_for_all_cases": models_used, "passed": passed, "results": results}, indent=2))
    return 0 if passed else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true", help="Require a configured model; fallback makes this evaluation fail")
    raise SystemExit(asyncio.run(evaluate(parser.parse_args().live)))
