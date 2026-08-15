from typing import Any

from pydantic import BaseModel, Field, field_validator


class TrialLocation(BaseModel):
    facility: str | None = None
    city: str | None = None
    state: str | None = None
    country: str | None = None
    zip_code: str | None = None
    latitude: float | None = None
    longitude: float | None = None

    def display(self) -> str:
        return ", ".join(part for part in (self.facility, self.city, self.state, self.country) if part)


class ClinicalTrial(BaseModel):
    nct_id: str
    title: str
    official_title: str | None = None
    brief_summary: str = ""
    detailed_description: str = ""
    eligibility_criteria: str = ""
    conditions: list[str] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)
    interventions: list[str] = Field(default_factory=list)
    phases: list[str] = Field(default_factory=list)
    study_type: str | None = None
    overall_status: str = "UNKNOWN"
    sex: str = "ALL"
    minimum_age: str | None = None
    maximum_age: str | None = None
    minimum_age_years: float | None = None
    maximum_age_years: float | None = None
    healthy_volunteers: bool | None = None
    locations: list[TrialLocation] = Field(default_factory=list)
    sponsor: str | None = None
    source_url: str
    last_updated: str | None = None
    raw: dict[str, Any] = Field(default_factory=dict, exclude=True)

    def searchable_text(self) -> str:
        sections = [
            f"Title: {self.title}",
            f"Conditions: {', '.join(self.conditions)}",
            f"Summary: {self.brief_summary}",
            f"Detailed description: {self.detailed_description}",
            f"Eligibility: {self.eligibility_criteria}",
            f"Interventions: {', '.join(self.interventions)}",
            f"Locations: {'; '.join(location.display() for location in self.locations)}",
        ]
        return "\n".join(section for section in sections if section.split(":", 1)[-1].strip())


class MatchRequest(BaseModel):
    query: str = Field(min_length=3, max_length=4000)
    age: float | None = Field(default=None, ge=0, le=125)
    condition: str | None = Field(default=None, max_length=200)
    location: str | None = Field(default=None, max_length=200)
    recruitment_status: list[str] = Field(default_factory=list)
    sex: str | None = Field(default=None, pattern="^(ALL|FEMALE|MALE)$")
    top_k: int = Field(default=10, ge=1, le=50)

    @field_validator("recruitment_status")
    @classmethod
    def normalize_statuses(cls, values: list[str]) -> list[str]:
        return [value.strip().upper().replace(" ", "_") for value in values if value.strip()]


class MatchResult(BaseModel):
    rank: int
    score: float
    semantic_score: float
    structured_score: float
    explanation: str
    trial: ClinicalTrial


class MatchResponse(BaseModel):
    query: str
    total_candidates: int
    matches: list[MatchResult]
    disclaimer: str = (
        "Research and portfolio demonstration only. This tool is not a certified medical device "
        "and must not be used for clinical decisions."
    )
