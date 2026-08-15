import json
from pathlib import Path

import httpx

from app.services.clinical_trials import ClinicalTrialsClient, age_to_years, parse_study


FIXTURE = Path(__file__).parent / "fixtures" / "study.json"


def test_age_to_years_supports_multiple_units():
    assert age_to_years("18 Years") == 18
    assert age_to_years("6 Months") == 0.5
    assert age_to_years(None) is None


def test_parse_study_extracts_matching_fields():
    trial = parse_study(json.loads(FIXTURE.read_text()))
    assert trial.nct_id == "NCT01234567"
    assert trial.minimum_age_years == 40
    assert trial.maximum_age_years == 75
    assert trial.conditions == ["Type 2 Diabetes", "Cardiovascular Disease"]
    assert trial.locations[0].state == "Texas"
    assert trial.interventions == ["DRUG - Investigational Therapy"]


def test_client_paginates_and_honors_max_studies():
    study = json.loads(FIXTURE.read_text())
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        if len(calls) == 1:
            return httpx.Response(200, json={"studies": [study], "nextPageToken": "next"})
        second = json.loads(json.dumps(study))
        second["protocolSection"]["identificationModule"]["nctId"] = "NCT07654321"
        return httpx.Response(200, json={"studies": [second]})

    client = ClinicalTrialsClient("https://example.test/api/v2", client=httpx.Client(transport=httpx.MockTransport(handler)))
    studies = list(client.iter_studies(page_size=1, max_studies=2))
    assert len(studies) == 2
    assert "pageToken=next" in str(calls[1].url)
