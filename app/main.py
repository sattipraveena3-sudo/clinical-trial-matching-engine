from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.config import Settings, get_settings
from app.models import ClinicalTrial, MatchRequest, MatchResponse
from app.services.embeddings import SentenceTransformerEmbedder
from app.services.matcher import TrialMatcher
from app.services.vector_store import TrialVectorStore


def build_matcher(settings: Settings) -> TrialMatcher:
    embedder = SentenceTransformerEmbedder(settings.embedding_model)
    store = TrialVectorStore(settings.chroma_dir, settings.collection_name, embedder)
    return TrialMatcher(store, settings.semantic_candidate_multiplier)


def create_app(matcher: TrialMatcher | None = None, settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        if not hasattr(app.state, "matcher"):
            app.state.matcher = matcher or build_matcher(settings)
        yield

    app = FastAPI(title=settings.app_name, version="1.0.0", lifespan=lifespan)
    static_dir = Path(__file__).parent / "static"
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

    @app.get("/", include_in_schema=False)
    def frontend() -> FileResponse:
        return FileResponse(static_dir / "index.html")

    @app.get("/health")
    def health(request: Request) -> dict:
        engine = request.app.state.matcher
        return {
            "status": "ok",
            "indexed_chunks": engine.vector_store.count(),
            "model": settings.embedding_model,
        }

    @app.post("/match", response_model=MatchResponse)
    def match_trials(payload: MatchRequest, request: Request) -> MatchResponse:
        return request.app.state.matcher.match(payload)

    @app.get("/trial/{nct_id}", response_model=ClinicalTrial)
    def get_trial(nct_id: str, request: Request) -> ClinicalTrial:
        trial = request.app.state.matcher.vector_store.get_trial(nct_id.upper())
        if trial is None:
            raise HTTPException(status_code=404, detail="Trial not found in the local index")
        return trial

    return app


app = create_app()
