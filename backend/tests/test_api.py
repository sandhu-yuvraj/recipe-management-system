import os
os.environ["DATABASE_URL"] = "sqlite:///./test.db"
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def auth():
    r = client.post("/auth/register", json={"email":"test@example.com","password":"testing1"})
    if r.status_code == 409:
        r = client.post("/auth/login", json={"email":"test@example.com","password":"testing1"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_create_and_expand():
    headers = auth()
    flour = {"name":"Flour","quantity":300,"unit":"g"}
    dough = client.post("/recipes", headers=headers, json={"name":"Dough","servings":2,"ingredients":[flour],"recipe_components":[]})
    assert dough.status_code == 201
    bread = client.post("/recipes", headers=headers, json={"name":"Bread","servings":1,"ingredients":[],"recipe_components":[{"recipe_id":dough.json()['id'],"quantity":2,"unit":"portion"}]})
    assert bread.status_code == 201
    expanded = client.get(f"/recipes/{bread.json()['id']}/expand", headers=headers)
    assert expanded.status_code == 200
    assert expanded.json()["ingredients"][0]["quantity"] == 600
