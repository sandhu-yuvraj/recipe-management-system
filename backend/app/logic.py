from collections import defaultdict
from fastapi import HTTPException
from sqlalchemy.orm import Session, selectinload
from .models import Ingredient, Recipe, RecipeComponent


def get_user_recipe(db: Session, user_id: int, recipe_id: int) -> Recipe:
    recipe = (
        db.query(Recipe)
        .options(selectinload(Recipe.components).selectinload(RecipeComponent.ingredient), selectinload(Recipe.components).selectinload(RecipeComponent.referenced_recipe))
        .filter(Recipe.id == recipe_id, Recipe.owner_id == user_id)
        .first()
    )
    if not recipe:
        raise HTTPException(status_code=404, detail="Recipe not found")
    return recipe


def would_create_cycle(db: Session, owner_id: int, parent_recipe_id: int, child_recipe_id: int) -> bool:
    if parent_recipe_id == child_recipe_id:
        return True
    stack = [child_recipe_id]
    seen: set[int] = set()
    while stack:
        current = stack.pop()
        if current in seen:
            continue
        seen.add(current)
        recipe = db.query(Recipe).filter(Recipe.id == current, Recipe.owner_id == owner_id).first()
        if not recipe:
            continue
        refs = db.query(RecipeComponent.referenced_recipe_id).filter(
            RecipeComponent.recipe_id == current,
            RecipeComponent.referenced_recipe_id.is_not(None),
        ).all()
        for (rid,) in refs:
            if rid == parent_recipe_id:
                return True
            stack.append(rid)
    return False


def add_ingredient(db: Session, name: str) -> Ingredient:
    normalized = name.strip()
    ing = db.query(Ingredient).filter(Ingredient.name.ilike(normalized)).first()
    if ing:
        return ing
    ing = Ingredient(name=normalized)
    db.add(ing)
    db.flush()
    return ing


def serialize_component(c: RecipeComponent) -> dict:
    if c.ingredient:
        return {"id": c.id, "type": "ingredient", "name": c.ingredient.name, "quantity": c.quantity, "unit": c.unit,
                "recipe_id": c.recipe_id, "ingredient_id": c.ingredient_id, "referenced_recipe_id": None}
    return {"id": c.id, "type": "recipe", "name": c.referenced_recipe.name, "quantity": c.quantity, "unit": c.unit,
            "recipe_id": c.recipe_id, "ingredient_id": None, "referenced_recipe_id": c.referenced_recipe_id}


def expand_recipe(db: Session, owner_id: int, recipe_id: int):
    recipe = get_user_recipe(db, owner_id, recipe_id)
    totals = defaultdict(float)
    visited_path: list[int] = []

    def walk(rid: int, multiplier: float, stack: set[int]):
        if rid in stack:
            cycle = " -> ".join(map(str, [*stack, rid]))
            raise HTTPException(status_code=400, detail=f"Circular dependency detected: {cycle}")
        r = get_user_recipe(db, owner_id, rid)
        next_stack = stack | {rid}
        for comp in r.components:
            if comp.ingredient_id and comp.ingredient:
                key = (comp.ingredient_id, comp.unit)
                totals[key] += comp.quantity * multiplier
            elif comp.referenced_recipe_id:
                walk(comp.referenced_recipe_id, multiplier * comp.quantity, next_stack)

    walk(recipe.id, 1.0, set())
    items = [
        {"ingredient_id": iid, "name": db.get(Ingredient, iid).name, "quantity": qty, "unit": unit}
        for (iid, unit), qty in sorted(totals.items(), key=lambda x: x[0][1])
    ]
    return items
