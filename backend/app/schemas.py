from typing import Literal
from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6)


class LoginRequest(RegisterRequest):
    pass


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class IngredientIn(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    quantity: float = Field(ge=0)
    unit: str = Field(min_length=1, max_length=50)


class RecipeRefIn(BaseModel):
    recipe_id: int
    quantity: float = Field(default=1, ge=0)
    unit: str = Field(default="portion", min_length=1, max_length=50)


class ComponentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    type: Literal["ingredient", "recipe"]
    name: str
    quantity: float
    unit: str
    recipe_id: int | None = None
    ingredient_id: int | None = None
    referenced_recipe_id: int | None = None


class RecipeCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: str | None = None
    servings: int = Field(default=1, ge=1)
    category: str | None = None
    vegetarian: bool = False
    vegan: bool = False
    preparation_time: int | None = Field(default=None, ge=0)
    cooking_time: int | None = Field(default=None, ge=0)
    difficulty: str | None = None
    ingredients: list[IngredientIn] = []
    recipe_components: list[RecipeRefIn] = []

    @model_validator(mode="after")
    def no_duplicate_empty(self):
        if not self.name.strip():
            raise ValueError("Recipe name cannot be blank")
        return self


class RecipeUpdate(RecipeCreate):
    pass


class RecipeListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    servings: int
    category: str | None
    updated_at: str | None


class RecipeDetail(BaseModel):
    id: int
    name: str
    description: str | None
    servings: int
    category: str | None
    vegetarian: bool
    vegan: bool
    preparation_time: int | None
    cooking_time: int | None
    difficulty: str | None
    components: list[ComponentOut]


class AddComponent(BaseModel):
    type: Literal["ingredient", "recipe"]
    name: str | None = None
    recipe_id: int | None = None
    quantity: float = Field(ge=0)
    unit: str = Field(min_length=1, max_length=50)


class ExpansionItem(BaseModel):
    ingredient_id: int
    name: str
    quantity: float
    unit: str


class ExpansionResponse(BaseModel):
    recipe_id: int
    recipe_name: str
    ingredients: list[ExpansionItem]
