from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.routers import market

app = FastAPI(
    title="Trading-Assistent",
    description="Forex-Analyse und Empfehlungen",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET"],
    allow_headers=["*"],
)

app.include_router(market.router)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}
