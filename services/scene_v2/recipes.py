from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class UniformRule:
    kind: str
    default: float
    min_value: float
    max_value: float
    max_update_hz: float


@dataclass(frozen=True)
class ShaderRecipe:
    recipe_id: str
    version: str
    backend_targets: tuple[str, ...]
    uniform_schema: dict[str, UniformRule]
    texture_slots: tuple[dict[str, Any], ...]


_RECIPES: dict[str, ShaderRecipe] = {
    "glass_refraction_like": ShaderRecipe(
        recipe_id="glass_refraction_like",
        version="1.0.0",
        backend_targets=("three-webgl",),
        uniform_schema={
            "ior": UniformRule("number", 1.18, 1.0, 1.6, 30.0),
            "distortion": UniformRule("number", 0.12, 0.0, 0.35, 30.0),
            "rim_strength": UniformRule("number", 0.45, 0.0, 1.0, 30.0),
        },
        texture_slots=(
            {"slot": "normalMap", "required": False, "max_dimension": 2048, "formats": ["png", "jpg", "webp"]},
        ),
    ),
    "water_volume_tint": ShaderRecipe(
        recipe_id="water_volume_tint",
        version="1.0.0",
        backend_targets=("three-webgl",),
        uniform_schema={
            "density": UniformRule("number", 0.36, 0.0, 1.0, 30.0),
            "blue_shift": UniformRule("number", 0.42, 0.0, 1.0, 30.0),
        },
        texture_slots=(),
    ),
    "caustic_overlay_shader": ShaderRecipe(
        recipe_id="caustic_overlay_shader",
        version="1.0.0",
        backend_targets=("three-webgl",),
        uniform_schema={
            "intensity": UniformRule("number", 0.5, 0.0, 1.0, 30.0),
            "scale": UniformRule("number", 1.6, 0.1, 4.0, 15.0),
            "speed": UniformRule("number", 0.8, 0.05, 3.0, 15.0),
        },
        texture_slots=(
            {"slot": "causticMap", "required": False, "max_dimension": 1024, "formats": ["png", "jpg", "webp"]},
        ),
    ),
}


def list_recipes() -> list[dict[str, Any]]:
    return [
        {
            "recipe_id": recipe.recipe_id,
            "version": recipe.version,
            "backend_targets": list(recipe.backend_targets),
            "uniform_schema": {
                name: {
                    "type": row.kind,
                    "default": row.default,
                    "min": row.min_value,
                    "max": row.max_value,
                    "max_update_hz": row.max_update_hz,
                }
                for name, row in recipe.uniform_schema.items()
            },
            "texture_slots": list(recipe.texture_slots),
        }
        for recipe in _RECIPES.values()
    ]


def get_recipe(recipe_id: str) -> ShaderRecipe | None:
    return _RECIPES.get(str(recipe_id))


def validate_uniform(recipe_id: str, uniform: str, value: Any) -> tuple[bool, str | None, float | None]:
    recipe = get_recipe(recipe_id)
    if recipe is None:
        return False, "unknown_recipe_id", None
    rule = recipe.uniform_schema.get(str(uniform))
    if rule is None:
        return False, "unknown_uniform", None
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return False, "uniform_not_numeric", None
    if numeric < rule.min_value or numeric > rule.max_value:
        return False, "uniform_out_of_range", None
    return True, None, numeric


__all__ = ["ShaderRecipe", "UniformRule", "get_recipe", "list_recipes", "validate_uniform"]
