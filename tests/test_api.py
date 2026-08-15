import json
from pathlib import Path

from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.models import MatchRequest, MatchResponse, MatchResult
from app.services.clinical_trials import parse_study


class FakeStore:
    def __init__(self, trial):
        self.trial = trial

    def count(self):
        return 3

    def get_trial(self, nct_id):
        return self.trial if nct_id == self.trial.nct_id else None


class FakeMatcher:
    def __init__(self, trial):
        self.vector_store = FakeStore(trial)

    def match(self, request: MatchRequest):
        return MatchResponse(
            query=request.query,
            total_candidates=1,
            matches=[MatchResult(rank=1, score=0.91, semantic_score=0.88, structured_score=1.0, explanation="Matched test trial.", trial=self.vector_store.trial)],
        )


def make_client(tmp_path):
    study = json.loads((Path(__file__).parent / "fixtures" / "study.json").read_text())
    trial = parse_study(study)
    settings = Settings(data_dir=tmp_path / "data", chroma_dir=tmp_path / "chroma")
    return TestClient(create_app(FakeMatcher(trial), settings))


def test_health_endpoint(tmp_path):
    with make_client(tmp_path) as client:
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json()["indexed_chunks"] == 3


def test_match_endpoint_returns_ranked_trial(tmp_path):
    with make_client(tmp_path) as client:
        response = client.post("/match", json={"query": "55 year old with diabetes in Texas", "age": 55, "top_k": 5})
        assert response.status_code == 200
        payload = response.json()
        assert payload["matches"][0]["trial"]["nct_id"] == "NCT01234567"
        assert payload["matches"][0]["rank"] == 1


def test_trial_endpoint_handles_success_and_missing(tmp_path):
    with make_client(tmp_path) as client:
        assert client.get("/trial/NCT01234567").status_code == 200
        assert client.get("/trial/NCT00000000").status_code == 404
