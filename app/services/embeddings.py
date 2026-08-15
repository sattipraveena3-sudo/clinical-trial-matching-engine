from dataclasses import dataclass
from typing import Protocol, Sequence

import numpy as np

from app.models import ClinicalTrial


class Encoder(Protocol):
    def encode(self, sentences: Sequence[str], **kwargs) -> np.ndarray: ...


@dataclass(frozen=True)
class TrialChunk:
    chunk_id: str
    nct_id: str
    section: str
    text: str


class TextChunker:
    def __init__(self, chunk_size: int = 900, overlap: int = 120):
        if chunk_size <= overlap or overlap < 0:
            raise ValueError("chunk_size must be greater than overlap")
        self.chunk_size = chunk_size
        self.overlap = overlap

    def split(self, text: str) -> list[str]:
        normalized = " ".join(text.split())
        if not normalized:
            return []
        chunks = []
        start = 0
        while start < len(normalized):
            end = min(start + self.chunk_size, len(normalized))
            if end < len(normalized):
                boundary = normalized.rfind(" ", start, end)
                if boundary > start + self.chunk_size // 2:
                    end = boundary
            chunks.append(normalized[start:end].strip())
            if end == len(normalized):
                break
            start = max(end - self.overlap, start + 1)
        return chunks

    def trial_chunks(self, trial: ClinicalTrial) -> list[TrialChunk]:
        sections = {
            "overview": "\n".join(
                [trial.title, ", ".join(trial.conditions), trial.brief_summary, trial.detailed_description]
            ),
            "eligibility": trial.eligibility_criteria,
            "interventions_locations": "\n".join(
                [
                    ", ".join(trial.interventions),
                    "; ".join(location.display() for location in trial.locations),
                ]
            ),
        }
        output = []
        for section, text in sections.items():
            for index, chunk in enumerate(self.split(text)):
                output.append(
                    TrialChunk(
                        chunk_id=f"{trial.nct_id}:{section}:{index}",
                        nct_id=trial.nct_id,
                        section=section,
                        text=chunk,
                    )
                )
        return output


class SentenceTransformerEmbedder:
    def __init__(self, model_name: str, encoder: Encoder | None = None):
        if encoder is None:
            from sentence_transformers import SentenceTransformer

            encoder = SentenceTransformer(model_name)
        self.encoder = encoder

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        if not texts:
            return []
        embeddings = self.encoder.encode(
            list(texts), normalize_embeddings=True, show_progress_bar=False, convert_to_numpy=True
        )
        return np.asarray(embeddings, dtype=np.float32).tolist()

    def embed_query(self, query: str) -> list[float]:
        return self.embed([query])[0]
