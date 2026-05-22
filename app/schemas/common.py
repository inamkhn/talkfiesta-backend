"""
TalkFiesta — Common Schemas
===========================
Shared response wrappers and enums used across modules.
"""
from __future__ import annotations

from enum import Enum
from typing import Generic, TypeVar

from pydantic import BaseModel


class ModuleContentStatus(str, Enum):
    ready = "ready"
    generating = "generating"
    empty = "empty"


T = TypeVar("T")


class ModuleContentResponse(BaseModel, Generic[T]):
    status: ModuleContentStatus
    items: list[T] = []
    message: str = ""
