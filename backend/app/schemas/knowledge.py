from typing import Annotated

from pydantic import BaseModel, Field, StringConstraints


RagflowId = Annotated[str, StringConstraints(pattern=r'^[a-fA-F0-9]{32}$')]


class DatasetCreate(BaseModel):
    name: str = Field(min_length=1, max_length=128)


class SearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=1000)
    top_k: int = Field(default=5, ge=1, le=20)
    dataset_ids: list[RagflowId] | None = Field(default=None, max_length=20)
    knowledge_base_ids: list[RagflowId] | None = Field(default=None, max_length=20)
    similarity_threshold: float = Field(default=0.2, ge=0, le=1)


class ParseRequest(BaseModel):
    document_ids: list[RagflowId] = Field(min_length=1, max_length=50)
