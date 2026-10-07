from datetime import datetime
from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .db import Base


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    recipes: Mapped[list["Recipe"]] = relationship(back_populates="owner", cascade="all, delete-orphan")


class Recipe(Base):
    __tablename__ = "recipes"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(255), index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    servings: Mapped[int] = mapped_column(Integer, default=1)
    category: Mapped[str | None] = mapped_column(String(100), nullable=True)
    vegetarian: Mapped[bool] = mapped_column(Boolean, default=False)
    vegan: Mapped[bool] = mapped_column(Boolean, default=False)
    preparation_time: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cooking_time: Mapped[int | None] = mapped_column(Integer, nullable=True)
    difficulty: Mapped[str | None] = mapped_column(String(50), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    owner: Mapped[User] = relationship(back_populates="recipes")
    components: Mapped[list["RecipeComponent"]] = relationship(back_populates="recipe", foreign_keys="RecipeComponent.recipe_id", cascade="all, delete-orphan")


class Ingredient(Base):
    __tablename__ = "ingredients"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), unique=True, index=True)


class RecipeComponent(Base):
    __tablename__ = "recipe_components"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    recipe_id: Mapped[int] = mapped_column(ForeignKey("recipes.id", ondelete="CASCADE"), index=True)
    ingredient_id: Mapped[int | None] = mapped_column(ForeignKey("ingredients.id", ondelete="CASCADE"), nullable=True)
    referenced_recipe_id: Mapped[int | None] = mapped_column(ForeignKey("recipes.id", ondelete="RESTRICT"), nullable=True)
    quantity: Mapped[float] = mapped_column(Float, default=0)
    unit: Mapped[str] = mapped_column(String(50), default="unit")
    recipe: Mapped[Recipe] = relationship(back_populates="components", foreign_keys=[recipe_id])
    ingredient: Mapped[Ingredient | None] = relationship(foreign_keys=[ingredient_id])
    referenced_recipe: Mapped[Recipe | None] = relationship(foreign_keys=[referenced_recipe_id])
    __table_args__ = (UniqueConstraint("recipe_id", "ingredient_id", "referenced_recipe_id", "unit", name="uq_component"),)
