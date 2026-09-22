from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.routers import (
    aisles,
    alternates,
    auth,
    drafts,
    finder,
    import_,
    ingredients,
    meal_plan,
    recipes,
    shopping_list,
    steps,
)

app = FastAPI(title="CookVault", version="0.1.0")

# Only mounted when explicitly configured -- see Settings.cors_origins.
if settings.cors_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

app.include_router(auth.router)
app.include_router(recipes.router)
app.include_router(drafts.router)
app.include_router(ingredients.router)
app.include_router(steps.router)
app.include_router(alternates.router)
app.include_router(shopping_list.router)
app.include_router(aisles.router)
app.include_router(meal_plan.router)
app.include_router(import_.router)
app.include_router(finder.router)


@app.get("/health")
def health():
    return {"status": "ok"}
