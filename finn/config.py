from functools import lru_cache
from pathlib import Path

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[1]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ROOT / ".env", extra="ignore", env_prefix="")

    gemini_api_key: SecretStr | None = None
    google_api_key: SecretStr | None = None
    gemini_model: str = "gemini-3.5-flash-lite"
    finn_data_dir: Path = ROOT / "data"
    finn_http_timeout: int = Field(default=30, ge=1, le=120)
    finn_max_pdf_mb: int = Field(default=30, ge=1, le=100)
    finn_max_model_calls: int = Field(default=6, ge=0, le=20)
    finn_chunk_chars: int = Field(default=18000, ge=4000, le=40000)

    @property
    def api_key(self) -> str | None:
        key = self.gemini_api_key or self.google_api_key
        return key.get_secret_value() if key else None


@lru_cache
def get_settings() -> Settings:
    return Settings()
