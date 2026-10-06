from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from .auth import create_token, current_user, hash_password, verify_password
from .config import settings
from .db import Base, engine, get_db
from .logic import add_ingredient, expand_recipe, get_user_recipe, serialize_component, would_create_cycle
from .models import Ingredient, Recipe, RecipeComponent, User
from .schemas import AddComponent, ExpansionResponse, LoginRequest, RecipeCreate, RecipeDetail, RecipeRefIn, RecipeUpdate, RegisterRequest, TokenResponse

Base.metadata.create_all(bind=engine)
app = FastAPI(title=settings.app_name, version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=[o.strip() for o in settings.cors_origins.split(",")], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])


def seed_demo(db: Session):
    if db.query(User).count():
        return
    user = User(email="demo@example.com", password_hash=hash_password("demo1234"))
    db.add(user); db.flush()
    tomato = Recipe(owner_id=user.id, name="Tomato Sauce", servings=4, category="Sauce")
    db.add(tomato); db.flush()
    for name, qty, unit in [("Tomatoes", 500, "g"), ("Garlic", 20, "g"), ("Olive Oil", 30, "ml"), ("Herbs", 5, "g")]:
        ing = add_ingredient(db, name)
        db.add(RecipeComponent(recipe_id=tomato.id, ingredient_id=ing.id, quantity=qty, unit=unit))
    pasta = Recipe(owner_id=user.id, name="Pasta Arrabbiata", servings=2, category="Main", difficulty="Easy")
    db.add(pasta); db.flush()
    db.add(RecipeComponent(recipe_id=pasta.id, ingredient_id=add_ingredient(db, "Pasta").id, quantity=200, unit="g"))
    db.add(RecipeComponent(recipe_id=pasta.id, referenced_recipe_id=tomato.id, quantity=0.5, unit="portion"))
    db.add(RecipeComponent(recipe_id=pasta.id, ingredient_id=add_ingredient(db, "Chilli").id, quantity=10, unit="g"))
    db.commit()

with Session(engine) as seed_db:
    try: seed_demo(seed_db)
    except Exception: seed_db.rollback()


@app.get("/health")
def health(): return {"status": "ok"}


@app.post("/auth/register", response_model=TokenResponse)
def register(payload: RegisterRequest, db: Session = Depends(get_db)):
    if db.query(User).filter(User.email == payload.email.lower()).first():
        raise HTTPException(409, "Email already registered")
    user = User(email=payload.email.lower(), password_hash=hash_password(payload.password))
    db.add(user); db.commit(); db.refresh(user)
    return TokenResponse(access_token=create_token(user.id))


@app.post("/auth/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == payload.email.lower()).first()
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(401, "Invalid email or password")
    return TokenResponse(access_token=create_token(user.id))


@app.get("/me")
def me(user: User = Depends(current_user)): return {"id": user.id, "email": user.email}


@app.get("/ingredients")
def ingredients(db: Session = Depends(get_db), user: User = Depends(current_user)):
    return [{"id": x.id, "name": x.name} for x in db.query(Ingredient).order_by(Ingredient.name).all()]


@app.get("/recipes")
def recipes(db: Session = Depends(get_db), user: User = Depends(current_user), q: str | None = None):
    query = db.query(Recipe).filter(Recipe.owner_id == user.id)
    if q: query = query.filter(Recipe.name.ilike(f"%{q}%"))
    return [{"id": r.id, "name": r.name, "servings": r.servings, "category": r.category, "updated_at": r.updated_at.isoformat() if r.updated_at else None} for r in query.order_by(Recipe.name).all()]


@app.get("/recipes/{recipe_id}", response_model=RecipeDetail)
def recipe_detail(recipe_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    recipe = get_user_recipe(db, user.id, recipe_id)
    return RecipeDetail(id=recipe.id, name=recipe.name, description=recipe.description, servings=recipe.servings,
        category=recipe.category, vegetarian=recipe.vegetarian, vegan=recipe.vegan, preparation_time=recipe.preparation_time,
        cooking_time=recipe.cooking_time, difficulty=recipe.difficulty,
        components=[serialize_component(c) for c in recipe.components])


def set_components(db: Session, recipe: Recipe, payload: RecipeCreate | RecipeUpdate):
    recipe.components.clear(); db.flush()
    for item in payload.ingredients:
        ing = add_ingredient(db, item.name)
        db.add(RecipeComponent(recipe_id=recipe.id, ingredient_id=ing.id, quantity=item.quantity, unit=item.unit))
    for item in payload.recipe_components:
        child = db.query(Recipe).filter(Recipe.id == item.recipe_id, Recipe.owner_id == recipe.owner_id).first()
        if not child: raise HTTPException(404, f"Referenced recipe {item.recipe_id} not found")
        if would_create_cycle(db, recipe.owner_id, recipe.id, child.id):
            raise HTTPException(400, "Circular recipe dependency is not allowed")
        db.add(RecipeComponent(recipe_id=recipe.id, referenced_recipe_id=child.id, quantity=item.quantity, unit=item.unit))


@app.post("/recipes", response_model=dict, status_code=201)
def create_recipe(payload: RecipeCreate, db: Session = Depends(get_db), user: User = Depends(current_user)):
    recipe = Recipe(owner_id=user.id, name=payload.name.strip(), description=payload.description, servings=payload.servings,
                    category=payload.category, vegetarian=payload.vegetarian, vegan=payload.vegan, preparation_time=payload.preparation_time,
                    cooking_time=payload.cooking_time, difficulty=payload.difficulty)
    db.add(recipe); db.flush(); set_components(db, recipe, payload); db.commit(); db.refresh(recipe)
    return {"id": recipe.id}


@app.put("/recipes/{recipe_id}", response_model=dict)
def update_recipe(recipe_id: int, payload: RecipeUpdate, db: Session = Depends(get_db), user: User = Depends(current_user)):
    recipe = get_user_recipe(db, user.id, recipe_id)
    recipe.name = payload.name.strip(); recipe.description = payload.description; recipe.servings = payload.servings; recipe.category = payload.category
    recipe.vegetarian = payload.vegetarian; recipe.vegan = payload.vegan; recipe.preparation_time = payload.preparation_time; recipe.cooking_time = payload.cooking_time; recipe.difficulty = payload.difficulty
    set_components(db, recipe, payload); db.commit(); return {"id": recipe.id}


@app.delete("/recipes/{recipe_id}")
def delete_recipe(recipe_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    recipe = get_user_recipe(db, user.id, recipe_id)
    used = db.query(RecipeComponent).filter(RecipeComponent.referenced_recipe_id == recipe.id).count()
    if used: raise HTTPException(409, "Recipe is used by another recipe and cannot be deleted")
    db.delete(recipe); db.commit(); return {"deleted": True}


@app.post("/recipes/{recipe_id}/components", response_model=dict, status_code=201)
def add_component(recipe_id: int, payload: AddComponent, db: Session = Depends(get_db), user: User = Depends(current_user)):
    recipe = get_user_recipe(db, user.id, recipe_id)
    if payload.type == "ingredient":
        if not payload.name: raise HTTPException(400, "Ingredient name is required")
        ing = add_ingredient(db, payload.name)
        c = RecipeComponent(recipe_id=recipe.id, ingredient_id=ing.id, quantity=payload.quantity, unit=payload.unit)
    else:
        if payload.recipe_id is None: raise HTTPException(400, "recipe_id is required")
        child = get_user_recipe(db, user.id, payload.recipe_id)
        if would_create_cycle(db, user.id, recipe.id, child.id): raise HTTPException(400, "Circular recipe dependency is not allowed")
        c = RecipeComponent(recipe_id=recipe.id, referenced_recipe_id=child.id, quantity=payload.quantity, unit=payload.unit)
    db.add(c); db.commit(); db.refresh(c); return {"id": c.id}


@app.put("/recipes/{recipe_id}/components/{component_id}")
def update_component(recipe_id: int, component_id: int, payload: AddComponent, db: Session = Depends(get_db), user: User = Depends(current_user)):
    recipe = get_user_recipe(db, user.id, recipe_id)
    c = db.query(RecipeComponent).filter(RecipeComponent.id == component_id, RecipeComponent.recipe_id == recipe.id).first()
    if not c: raise HTTPException(404, "Component not found")
    if payload.type == "ingredient":
        if not payload.name: raise HTTPException(400, "Ingredient name is required")
        c.ingredient_id = add_ingredient(db, payload.name).id; c.referenced_recipe_id = None
    else:
        if payload.recipe_id is None: raise HTTPException(400, "recipe_id is required")
        child = get_user_recipe(db, user.id, payload.recipe_id)
        if would_create_cycle(db, user.id, recipe.id, child.id): raise HTTPException(400, "Circular recipe dependency is not allowed")
        c.referenced_recipe_id = child.id; c.ingredient_id = None
    c.quantity = payload.quantity; c.unit = payload.unit; db.commit(); return {"updated": True}


@app.delete("/recipes/{recipe_id}/components/{component_id}")
def delete_component(recipe_id: int, component_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    get_user_recipe(db, user.id, recipe_id)
    c = db.query(RecipeComponent).filter(RecipeComponent.id == component_id, RecipeComponent.recipe_id == recipe_id).first()
    if not c: raise HTTPException(404, "Component not found")
    db.delete(c); db.commit(); return {"deleted": True}


@app.get("/recipes/{recipe_id}/expand", response_model=ExpansionResponse)
def expansion(recipe_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    recipe = get_user_recipe(db, user.id, recipe_id)
    return ExpansionResponse(recipe_id=recipe.id, recipe_name=recipe.name, ingredients=expand_recipe(db, user.id, recipe.id))
