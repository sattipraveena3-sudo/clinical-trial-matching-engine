import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Iterator

import httpx

from app.models import ClinicalTrial, TrialLocation


AGE_PATTERN = re.compile(r"(?P<value>\d+(?:\.\d+)?)\s*(?P<unit>Years?|Months?|Weeks?|Days?)", re.I)


def age_to_years(value: str | None) -> float | None:
    if not value or value.upper() in {"N/A", "NA", "NONE"}:
        return None
    match = AGE_PATTERN.search(value)
    if not match:
        return None
    number = float(match.group("value"))
    unit = match.group("unit").lower()
    if unit.startswith("month"):
        return number / 12
    if unit.startswith("week"):
        return number / 52.1429
    if unit.startswith("day"):
        return number / 365.25
    return number


def _get(mapping: dict, *keys: str, default=None):
    current = mapping
    for key in keys:
        if not isinstance(current, dict):
            return default
        current = current.get(key)
    return default if current is None else current


def parse_study(study: dict) -> ClinicalTrial:
    protocol = study.get("protocolSection", {})
    identification = protocol.get("identificationModule", {})
    status = protocol.get("statusModule", {})
    description = protocol.get("descriptionModule", {})
    conditions = protocol.get("conditionsModule", {})
    design = protocol.get("designModule", {})
    eligibility = protocol.get("eligibilityModule", {})
    contacts = protocol.get("contactsLocationsModule", {})
    sponsors = protocol.get("sponsorCollaboratorsModule", {})
    interventions_module = protocol.get("armsInterventionsModule", {})

    nct_id = identification.get("nctId")
    if not nct_id:
        raise ValueError("ClinicalTrials.gov study is missing nctId")

    locations = []
    for location in contacts.get("locations", []) or []:
        geo = location.get("geoPoint", {}) or {}
        locations.append(
            TrialLocation(
                facility=location.get("facility"),
                city=location.get("city"),
                state=location.get("state"),
                country=location.get("country"),
                zip_code=location.get("zip"),
                latitude=geo.get("lat"),
                longitude=geo.get("lon"),
            )
        )

    interventions = []
    for intervention in interventions_module.get("interventions", []) or []:
        label = " - ".join(
            item for item in (intervention.get("type"), intervention.get("name")) if item
        )
        if label:
            interventions.append(label)

    minimum_age = eligibility.get("minimumAge")
    maximum_age = eligibility.get("maximumAge")
    lead_sponsor = sponsors.get("leadSponsor", {}) or {}
    phases = design.get("phases", []) or []

    return ClinicalTrial(
        nct_id=nct_id,
        title=identification.get("briefTitle") or identification.get("officialTitle") or nct_id,
        official_title=identification.get("officialTitle"),
        brief_summary=description.get("briefSummary", ""),
        detailed_description=description.get("detailedDescription", ""),
        eligibility_criteria=eligibility.get("eligibilityCriteria", ""),
        conditions=conditions.get("conditions", []) or [],
        keywords=conditions.get("keywords", []) or [],
        interventions=interventions,
        phases=phases,
        study_type=design.get("studyType"),
        overall_status=status.get("overallStatus", "UNKNOWN"),
        sex=eligibility.get("sex", "ALL"),
        minimum_age=minimum_age,
        maximum_age=maximum_age,
        minimum_age_years=age_to_years(minimum_age),
        maximum_age_years=age_to_years(maximum_age),
        healthy_volunteers=eligibility.get("healthyVolunteers"),
        locations=locations,
        sponsor=lead_sponsor.get("name"),
        source_url=f"https://clinicaltrials.gov/study/{nct_id}",
        last_updated=_get(status, "lastUpdatePostDateStruct", "date")
        or _get(status, "studyFirstPostDateStruct", "date")
        or _get(status, "studyFirstSubmitDate"),
        raw=study,
    )


class ClinicalTrialsClient:
    def __init__(self, base_url: str, timeout: float = 45.0, client: httpx.Client | None = None):
        self.base_url = base_url.rstrip("/")
        self.client = client or httpx.Client(timeout=timeout, follow_redirects=True)

    def iter_studies(
        self,
        query: str = "AREA[OverallStatus]RECRUITING OR AREA[OverallStatus]NOT_YET_RECRUITING OR AREA[OverallStatus]ENROLLING_BY_INVITATION OR AREA[OverallStatus]ACTIVE_NOT_RECRUITING",
        page_size: int = 100,
        max_studies: int | None = None,
    ) -> Iterator[dict]:
        yielded = 0
        page_token = None
        while True:
            params = {"query.term": query, "pageSize": min(page_size, 1000), "format": "json"}
            if page_token:
                params["pageToken"] = page_token
            response = self.client.get(f"{self.base_url}/studies", params=params)
            response.raise_for_status()
            payload = response.json()
            for study in payload.get("studies", []):
                yield study
                yielded += 1
                if max_studies is not None and yielded >= max_studies:
                    return
            page_token = payload.get("nextPageToken")
            if not page_token:
                return

    def fetch_study(self, nct_id: str) -> dict:
        response = self.client.get(f"{self.base_url}/studies/{nct_id}", params={"format": "json"})
        response.raise_for_status()
        return response.json()


def save_trials(studies: list[dict], raw_dir: Path, processed_dir: Path) -> tuple[Path, Path, list[ClinicalTrial]]:
    raw_dir.mkdir(parents=True, exist_ok=True)
    processed_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    raw_path = raw_dir / f"clinical_trials_{timestamp}.json"
    processed_path = processed_dir / "trials.jsonl"
    trials = [parse_study(study) for study in studies]
    raw_path.write_text(
        json.dumps({"downloaded_at": timestamp, "studies": studies}, indent=2),
        encoding="utf-8",
    )
    with processed_path.open("w", encoding="utf-8") as stream:
        for trial in trials:
            stream.write(trial.model_dump_json(exclude={"raw"}) + "\n")
    return raw_path, processed_path, trials


def load_processed_trials(path: Path) -> list[ClinicalTrial]:
    if not path.exists():
        return []
    return [
        ClinicalTrial.model_validate_json(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
