import json
from pathlib import Path

import numpy as np

from app.services.clinical_trials import parse_study
from app.services.embeddings import SentenceTransformerEmbedder, TextChunker


class FakeEncoder:
    def encode(self, sentences, **kwargs):
        return np.asarray([[len(text), text.count("diabetes"), 1.0] for text in sentences], dtype=np.float32)


def test_chunker_respects_size_and_overlap():
    chunks = TextChunker(chunk_size=40, overlap=8).split("word " * 40)
    assert len(chunks) > 1
    assert all(len(chunk) <= 40 for chunk in chunks)


def test_trial_chunking_and_embedding_are_complete():
    study = json.loads((Path(__file__).parent / "fixtures" / "study.json").read_text())
    trial = parse_study(study)
    chunks = TextChunker(chunk_size=120, overlap=20).trial_chunks(trial)
    assert {chunk.section for chunk in chunks} == {"overview", "eligibility", "interventions_locations"}
    embedder = SentenceTransformerEmbedder("test-model", encoder=FakeEncoder())
    vectors = embedder.embed([chunk.text for chunk in chunks])
    assert len(vectors) == len(chunks)
    assert all(len(vector) == 3 for vector in vectors)
