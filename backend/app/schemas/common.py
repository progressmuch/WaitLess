"""Common response envelopes.

docs/05-api-specification.md section 12 requires a consistent response shape:

    {"data": {...}, "message": "Success"}
"""

from typing import Generic, TypeVar

from pydantic import BaseModel, Field

DataT = TypeVar("DataT")


class APIResponse(BaseModel, Generic[DataT]):
    """Successful response wrapper: payload under `data`, human message."""

    data: DataT = Field(default=None)
    message: str = "Success"


class MessageAPIResponse(BaseModel):
    """Response for endpoints that return no payload."""

    message: str = "Success"