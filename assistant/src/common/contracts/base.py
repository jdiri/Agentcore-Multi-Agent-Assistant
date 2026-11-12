"""Shared tool result envelope. Tool data is never proof of authorization."""

from enum import StrEnum
from typing import Generic, Self, TypeVar

from pydantic import BaseModel, ConfigDict, Field, model_validator


class StrictContract(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class ToolStatus(StrEnum):
    OK = "ok"
    NOT_FOUND = "not_found"
    ERROR = "error"


class ToolError(StrictContract):
    code: str = Field(min_length=1)
    message: str = Field(min_length=1)


T = TypeVar("T")


class ToolResult(StrictContract, Generic[T]):
    """Successful empty collection = data=[]; missing singular record = not_found."""

    status: ToolStatus
    data: T | None = None
    error: ToolError | None = None
    synthetic: bool = True

    @model_validator(mode="after")
    def coherent(self) -> Self:
        if self.synthetic is not True:
            raise ValueError("Project 3 tool data must be marked synthetic")
        if self.status is ToolStatus.OK and (self.data is None or self.error is not None):
            raise ValueError("ok requires non-null data and no error")
        if self.status is ToolStatus.NOT_FOUND and (
            self.data is not None or self.error is not None
        ):
            raise ValueError("not_found requires null data and no error")
        if self.status is ToolStatus.ERROR and (self.error is None or self.data is not None):
            raise ValueError("error requires a ToolError and null data")
        return self
