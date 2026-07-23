"""Pydantic schemas for category catalog endpoints."""
from __future__ import annotations

from pydantic import BaseModel, Field


class CategoryRow(BaseModel):
    id: int
    name: str
    is_system: bool
    parent: str | None = None
    color: str | None
    icon: str | None
    usage_count: int = 0

    model_config = {"from_attributes": True}


class CategoryCreate(BaseModel):
    name: str = Field(min_length=1, max_length=64)
    parent: str | None = Field(default=None, max_length=64)
    color: str | None = Field(default=None, max_length=16)
    icon: str | None = Field(default=None, max_length=32)


class CategoryUpdate(BaseModel):
    color: str | None = Field(default=None, max_length=16)
    icon: str | None = Field(default=None, max_length=32)
