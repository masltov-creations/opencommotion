from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError
from jsonschema.validators import RefResolver

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SCHEMA_ROOT = PROJECT_ROOT / "packages" / "protocol" / "schemas"


@dataclass
class ProtocolValidationError(Exception):
    schema_path: str
    issues: list[dict[str, str]]

    def __str__(self) -> str:
        return f"Schema validation failed for {self.schema_path}: {len(self.issues)} issue(s)"


class ProtocolValidator:
    def __init__(self, schema_root: Path | None = None) -> None:
        self.schema_root = schema_root or SCHEMA_ROOT

    @lru_cache(maxsize=64)
    def _load_schema(self, schema_path: str) -> dict[str, Any]:
        path = (self.schema_root / schema_path).resolve()
        return json.loads(path.read_text())

    @lru_cache(maxsize=64)
    def _validator(self, schema_path: str) -> Draft202012Validator:
        path = (self.schema_root / schema_path).resolve()
        schema = self._load_schema(schema_path)
        resolver = RefResolver(base_uri=path.as_uri(), referrer=schema)
        return Draft202012Validator(schema=schema, resolver=resolver)

    def validate(self, schema_path: str, payload: Any) -> None:
        validator = self._validator(schema_path)
        errors = sorted(
            validator.iter_errors(payload),
            key=lambda e: list(e.path),
        )
        if not errors:
            return
        raise ProtocolValidationError(
            schema_path=schema_path,
            issues=[self._format_error(err) for err in errors],
        )

    @staticmethod
    def _format_error(error: ValidationError) -> dict[str, str]:
        if error.absolute_path:
            path = ".".join(str(part) for part in error.absolute_path)
        else:
            path = "$"
        return {
            "path": path,
            "message": error.message,
        }
