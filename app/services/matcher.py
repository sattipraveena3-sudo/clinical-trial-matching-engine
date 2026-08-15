from collections import defaultdict

from app.models import ClinicalTrial, MatchRequest, MatchResponse, MatchResult
from app.services.vector_store import TrialVectorStore


def _contains(value: str | None, query: str | None) -> bool:
    return not query or query.casefold() in (value or "").casefold()


class TrialMatcher:
    def __init__(self, vector_store: TrialVectorStore, candidate_multiplier: int = 8):
        self.vector_store = vector_store
        self.candidate_multiplier = candidate_multiplier

    @staticmethod
    def eligible_for_age(trial: ClinicalTrial, age: float | None) -> bool:
        if age is None:
            return True
        if trial.minimum_age_years is not None and age < trial.minimum_age_years:
            return False
        if trial.maximum_age_years is not None and age > trial.maximum_age_years:
            return False
        return True

    @staticmethod
    def passes_filters(trial: ClinicalTrial, request: MatchRequest) -> bool:
        if not TrialMatcher.eligible_for_age(trial, request.age):
            return False
        if request.sex and trial.sex not in {"ALL", request.sex}:
            return False
        if request.recruitment_status and trial.overall_status not in request.recruitment_status:
            return False
        if request.condition and not any(_contains(condition, request.condition) for condition in trial.conditions):
            return False
        if request.location and not any(_contains(location.display(), request.location) for location in trial.locations):
            return False
        return True

    @staticmethod
    def structured_score(trial: ClinicalTrial, request: MatchRequest) -> float:
        checks = []
        if request.age is not None:
            checks.append(1.0 if TrialMatcher.eligible_for_age(trial, request.age) else 0.0)
        if request.sex:
            checks.append(1.0 if trial.sex in {"ALL", request.sex} else 0.0)
        if request.condition:
            checks.append(1.0 if any(_contains(c, request.condition) for c in trial.conditions) else 0.0)
        if request.location:
            checks.append(1.0 if any(_contains(loc.display(), request.location) for loc in trial.locations) else 0.0)
        if request.recruitment_status:
            checks.append(1.0 if trial.overall_status in request.recruitment_status else 0.0)
        return sum(checks) / len(checks) if checks else 1.0

    @staticmethod
    def explanation(trial: ClinicalTrial, request: MatchRequest, best_section: str) -> str:
        reasons = []
        if request.condition:
            matched = [condition for condition in trial.conditions if _contains(condition, request.condition)]
            if matched:
                reasons.append(f"condition alignment with {', '.join(matched[:2])}")
        if request.age is not None:
            age_range = " to ".join(filter(None, [trial.minimum_age, trial.maximum_age]))
            reasons.append(f"age {request.age:g} falls within the listed range{f' ({age_range})' if age_range else ''}")
        if request.location:
            location = next((loc.display() for loc in trial.locations if _contains(loc.display(), request.location)), None)
            if location:
                reasons.append(f"a study location is available at {location}")
        if request.recruitment_status:
            reasons.append(f"status is {trial.overall_status.replace('_', ' ').title()}")
        section_label = best_section.replace("_", " ")
        reasons.append(f"the strongest semantic evidence came from the {section_label} text")
        return "Matched because " + "; ".join(reasons) + ". Eligibility must be confirmed by the study team."

    def match(self, request: MatchRequest) -> MatchResponse:
        requested_candidates = max(request.top_k * self.candidate_multiplier, 40)
        hits = self.vector_store.search(request.query, requested_candidates)
        grouped: dict[str, list[dict]] = defaultdict(list)
        for hit in hits:
            grouped[hit["metadata"]["nct_id"]].append(hit)

        ranked = []
        for nct_id, trial_hits in grouped.items():
            trial = ClinicalTrial.model_validate_json(trial_hits[0]["metadata"]["trial_json"])
            if not self.passes_filters(trial, request):
                continue
            best_hit = max(trial_hits, key=lambda item: item["semantic_score"])
            semantic = best_hit["semantic_score"]
            structured = self.structured_score(trial, request)
            final_score = 0.78 * semantic + 0.22 * structured
            ranked.append((final_score, semantic, structured, best_hit["metadata"]["section"], trial))

        ranked.sort(key=lambda item: item[0], reverse=True)
        matches = [
            MatchResult(
                rank=index,
                score=round(score, 4),
                semantic_score=round(semantic, 4),
                structured_score=round(structured, 4),
                explanation=self.explanation(trial, request, section),
                trial=trial,
            )
            for index, (score, semantic, structured, section, trial) in enumerate(ranked[: request.top_k], 1)
        ]
        return MatchResponse(query=request.query, total_candidates=len(grouped), matches=matches)
