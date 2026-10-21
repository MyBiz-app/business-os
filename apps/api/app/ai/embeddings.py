"""Search by meaning for the agents' libraries (slice C3a): the embeddings provider.

Built but off. An embedding turns a piece of text into numbers so that texts with a similar
meaning are close to each other; the library then finds chunks by meaning and not only by words.
It costs money (a provider such as Voyage AI charges per token), so by default nothing is embedded
and the library searches by words only. To switch it on, see docs/deploy/go-live-checklist.md."""

import json
import urllib.error
import urllib.request
from typing import Protocol

from app.core.config import get_settings

DIMENSIONS = 1024  # the size of the `embedding` column in the database
VOYAGE_URL = "https://api.voyageai.com/v1/embeddings"
VOYAGE_MODEL = "voyage-3"
BATCH = 64


class EmbeddingsUnavailable(Exception):
    """The provider could not be reached or refused; the library falls back to words."""


class EmbeddingProvider(Protocol):
    def embed(self, texts: list[str], *, query: bool) -> list[list[float]]: ...


class VoyageEmbeddings:
    """Voyage AI over HTTPS. `query`: the text is a question, not a document."""

    def __init__(self, api_key: str) -> None:
        self.api_key = api_key

    def embed(self, texts: list[str], *, query: bool) -> list[list[float]]:
        vectors: list[list[float]] = []
        for start in range(0, len(texts), BATCH):
            payload = {
                "input": texts[start : start + BATCH],
                "model": VOYAGE_MODEL,
                "input_type": "query" if query else "document",
                "output_dimension": DIMENSIONS,
            }
            request = urllib.request.Request(
                VOYAGE_URL,
                data=json.dumps(payload).encode(),
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                method="POST",
            )
            try:
                with urllib.request.urlopen(request, timeout=30) as response:  # noqa: S310
                    data = json.load(response)
            except (urllib.error.URLError, TimeoutError, ValueError) as error:
                raise EmbeddingsUnavailable(str(error)) from error
            vectors.extend(item["embedding"] for item in data["data"])
        return vectors


def provider() -> EmbeddingProvider | None:
    """The embeddings provider, or None while it is switched off (the default)."""
    settings = get_settings()
    if settings.kb_embeddings_provider == "voyage" and settings.voyage_api_key:
        return VoyageEmbeddings(settings.voyage_api_key.get_secret_value())
    return None


def as_sql(vector: list[float]) -> str:
    """A vector as pgvector reads it: '[0.1,0.2,...]'."""
    return "[" + ",".join(f"{x:.6g}" for x in vector) + "]"
