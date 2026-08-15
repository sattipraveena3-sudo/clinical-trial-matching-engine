import json
from pathlib import Path

import chromadb

from app.models import ClinicalTrial
from app.services.embeddings import SentenceTransformerEmbedder, TextChunker


class TrialVectorStore:
    def __init__(
        self,
        persist_directory: Path,
        collection_name: str,
        embedder: SentenceTransformerEmbedder,
        chunker: TextChunker | None = None,
    ):
        persist_directory.mkdir(parents=True, exist_ok=True)
        self.client = chromadb.PersistentClient(path=str(persist_directory))
        self.collection = self.client.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"},
        )
        self.embedder = embedder
        self.chunker = chunker or TextChunker()

    def count(self) -> int:
        return self.collection.count()

    def rebuild(self, trials: list[ClinicalTrial], batch_size: int = 128) -> int:
        name = self.collection.name
        try:
            self.client.delete_collection(name)
        except Exception:
            pass
        self.collection = self.client.create_collection(name=name, metadata={"hnsw:space": "cosine"})
        records = []
        for trial in trials:
            for chunk in self.chunker.trial_chunks(trial):
                records.append((trial, chunk))
        for start in range(0, len(records), batch_size):
            batch = records[start : start + batch_size]
            documents = [chunk.text for _, chunk in batch]
            self.collection.add(
                ids=[chunk.chunk_id for _, chunk in batch],
                documents=documents,
                embeddings=self.embedder.embed(documents),
                metadatas=[
                    {
                        "nct_id": trial.nct_id,
                        "section": chunk.section,
                        "overall_status": trial.overall_status,
                        "sex": trial.sex,
                        "conditions_text": " | ".join(trial.conditions).lower(),
                        "locations_text": " | ".join(location.display() for location in trial.locations).lower(),
                        "trial_json": trial.model_dump_json(exclude={"raw"}),
                    }
                    for trial, chunk in batch
                ],
            )
        return len(records)

    def search(self, query: str, n_results: int) -> list[dict]:
        if self.count() == 0:
            return []
        result = self.collection.query(
            query_embeddings=[self.embedder.embed_query(query)],
            n_results=min(n_results, self.count()),
            include=["metadatas", "documents", "distances"],
        )
        hits = []
        for metadata, document, distance in zip(
            result["metadatas"][0], result["documents"][0], result["distances"][0]
        ):
            hits.append(
                {
                    "metadata": metadata,
                    "document": document,
                    "distance": float(distance),
                    "semantic_score": max(0.0, min(1.0, 1.0 - float(distance))),
                }
            )
        return hits

    def get_trial(self, nct_id: str) -> ClinicalTrial | None:
        result = self.collection.get(where={"nct_id": nct_id}, include=["metadatas"], limit=1)
        if not result.get("metadatas"):
            return None
        return ClinicalTrial.model_validate_json(result["metadatas"][0]["trial_json"])
