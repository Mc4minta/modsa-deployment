from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal
from urllib.parse import urlparse

from dotenv import load_dotenv
from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


load_dotenv()

DEFAULT_OPENAI_COMPAT_KEY = "sk-local-placeholder"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    llm_base_url: str = Field(default="https://api.openai.com/v1", alias="LLM_BASE_URL")
    llm_api_key: str | None = Field(
        default=None,
        validation_alias=AliasChoices("LLM_API_KEY", "OPENAI_API_KEY"),
    )
    llm_model: str = Field(default="gpt-4o-mini", alias="LLM_MODEL")
    llm_timeout: float = Field(default=30.0, alias="LLM_TIMEOUT")
    llm_max_retries: int = Field(default=2, alias="LLM_MAX_RETRIES")

    embedding_provider: Literal["ollama", "huggingface", "openai"] = Field(
        default="ollama",
        alias="EMBEDDING_PROVIDER",
    )
    embedding_base_url: str = Field(
        default="https://api.openai.com/v1",
        alias="EMBEDDING_BASE_URL",
    )
    embedding_api_key: str | None = Field(
        default=None,
        validation_alias=AliasChoices("EMBEDDING_API_KEY", "OPENAI_API_KEY"),
    )
    embedding_model: str = Field(
        default="text-embedding-3-small",
        alias="EMBEDDING_MODEL",
    )
    embedding_timeout: float = Field(default=30.0, alias="EMBEDDING_TIMEOUT")
    embedding_max_retries: int = Field(default=2, alias="EMBEDDING_MAX_RETRIES")

    chroma_dir: Path = Field(default=Path("chroma_db"), alias="CHROMA_DIR")
    chroma_collection: str = Field(default="modsa_kmutt", alias="CHROMA_COLLECTION")
    rag_source_paths: str = Field(default="chunks", alias="RAG_SOURCE_PATHS")
    chunk_size: int = Field(default=1000, alias="CHUNK_SIZE")
    chunk_overlap: int = Field(default=150, alias="CHUNK_OVERLAP")
    retrieval_k: int = Field(default=4, alias="RETRIEVAL_K")
    retrieval_min_relevance: float = Field(
        default=0.35,
        alias="RETRIEVAL_MIN_RELEVANCE",
    )

    app_host: str = Field(default="127.0.0.1", alias="APP_HOST")
    app_port: int = Field(default=8000, alias="APP_PORT")
    cors_origins: str = Field(
        default="http://localhost:5173,http://127.0.0.1:5173",
        alias="CORS_ORIGINS",
    )
    admin_api_key: str | None = Field(default=None, alias="ADMIN_API_KEY")

    @property
    def source_paths(self) -> list[Path]:
        return [
            Path(item.strip())
            for item in self.rag_source_paths.split(",")
            if item.strip()
        ]

    @property
    def resolved_cors_origins(self) -> list[str]:
        return [item.strip() for item in self.cors_origins.split(",") if item.strip()]

    @property
    def resolved_llm_api_key(self) -> str:
        return self.llm_api_key or DEFAULT_OPENAI_COMPAT_KEY

    @property
    def resolved_embedding_api_key(self) -> str:
        if self.embedding_provider == "huggingface" and not self.embedding_api_key:
            raise ValueError(
                "EMBEDDING_PROVIDER=huggingface requires EMBEDDING_API_KEY "
                "(a Hugging Face access token) — refusing to fall back to a placeholder key."
            )
        return (
            self.embedding_api_key
            or self.llm_api_key
            or DEFAULT_OPENAI_COMPAT_KEY
        )

    @property
    def resolved_embedding_base_url(self) -> str:
        if self.embedding_provider == "ollama":
            parsed = urlparse(self.embedding_base_url)
            return f"{parsed.scheme}://{parsed.hostname}:{parsed.port}"
        return self.embedding_base_url


@lru_cache
def get_settings() -> Settings:
    return Settings()
