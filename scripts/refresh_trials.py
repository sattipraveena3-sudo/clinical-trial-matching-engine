import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.config import get_settings
from app.services.clinical_trials import ClinicalTrialsClient, save_trials
from app.services.embeddings import SentenceTransformerEmbedder
from app.services.vector_store import TrialVectorStore


def main() -> None:
    settings = get_settings()
    parser = argparse.ArgumentParser(description="Refresh and index public ClinicalTrials.gov studies")
    parser.add_argument("--query", default="AREA[OverallStatus]RECRUITING OR AREA[OverallStatus]NOT_YET_RECRUITING")
    parser.add_argument("--max-studies", type=int, default=settings.default_max_studies)
    parser.add_argument("--page-size", type=int, default=settings.default_page_size)
    args = parser.parse_args()

    client = ClinicalTrialsClient(settings.api_base_url)
    raw_studies = list(client.iter_studies(args.query, args.page_size, args.max_studies))
    raw_path, processed_path, trials = save_trials(raw_studies, settings.raw_dir, settings.processed_dir)
    embedder = SentenceTransformerEmbedder(settings.embedding_model)
    store = TrialVectorStore(settings.chroma_dir, settings.collection_name, embedder)
    chunks = store.rebuild(trials)
    print(json.dumps({"studies": len(trials), "chunks": chunks, "raw": str(raw_path), "processed": str(processed_path)}, indent=2))


if __name__ == "__main__":
    main()
