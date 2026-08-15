from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Clinical Trial Matching Engine"
    api_base_url: str = "https://clinicaltrials.gov/api/v2"
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    collection_name: str = "clinical_trials"
    data_dir: Path = Path("data")
    chroma_dir: Path = Path("data/chroma")
    default_page_size: int = 100
    default_max_studies: int = 1000
    semantic_candidate_multiplier: int = 8
    model_config = SettingsConfigDict(env_file=".env", env_prefix="CTME_", extra="ignore")

    @property
    def raw_dir(self) -> Path:
        return self.data_dir / "raw"

    @property
    def processed_dir(self) -> Path:
        return self.data_dir / "processed"

    def ensure_directories(self) -> None:
        for directory in (self.raw_dir, self.processed_dir, self.chroma_dir):
            directory.mkdir(parents=True, exist_ok=True)


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.ensure_directories()
    return settings
