"""Versioned HTTP requests. Compiler bundles retain their own schema version."""
from typing import Literal, Union

from pydantic import BaseModel, ConfigDict, Field, field_validator


class QueryRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    v: Literal[1] = 1
    frontend_id: Literal["sql", "builder", "nl", "elastic"] = "sql"
    backend: Literal["fixtures", "sqlite", "kb_db"] = "fixtures"
    source: str = Field(min_length=1, max_length=16384)
    verify: bool = True

    @field_validator("v", mode="before")
    @classmethod
    def exact_version(cls, value):
        if type(value) is not int:
            raise ValueError("v must be the integer 1")
        return value


class DatasetRequest(BaseModel):
    """Select a preloaded fixture set, or re-select the current one to reset."""
    model_config = ConfigDict(extra="forbid", strict=True)

    v: Literal[1] = 1
    dataset: str = Field(min_length=1, max_length=64, pattern=r"^[a-z0-9][a-z0-9-]*$")


class InsertRequest(BaseModel):
    """Append rows to the session dataset. Values must be exact ints or strings."""
    model_config = ConfigDict(extra="forbid", strict=True)

    v: Literal[1] = 1
    table: str = Field(min_length=1, max_length=64, pattern=r"^[a-z_][a-z0-9_]*$")
    rows: list[list[Union[int, str]]] = Field(min_length=1, max_length=1000)

    @field_validator("rows")
    @classmethod
    def uniform_width(cls, rows):
        widths = {len(row) for row in rows}
        if len(widths) != 1:
            raise ValueError("every row must have the same number of values")
        return rows
