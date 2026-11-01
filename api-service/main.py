import logging
import os
import httpx

from fastapi import FastAPI, HTTPException

app = FastAPI(title="NT533 Group10 - API Service")

logger = logging.getLogger("uvicorn.error")

# Dia chi Catalogue Service
CATALOGUE_BASE_URL = os.getenv(
    "CATALOGUE_BASE_URL",
    "http://127.0.0.1:8001"
)


@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": "api-service"
    }

@app.get("/ready")
def readiness():
    return {
        "status": "ready",
        "service": "api-service"
    }



@app.get("/products")
async def get_products():
    url = f"{CATALOGUE_BASE_URL.rstrip('/')}/products"

    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            response = await client.get(url)
            response.raise_for_status()

            logger.info(
    "Catalogue Service responded with HTTP %s",
    response.status_code
)

        return response.json()

    except httpx.TimeoutException:
        raise HTTPException(
            status_code=504,
            detail="Catalogue Service timeout"
        )

    except httpx.HTTPStatusError:
        raise HTTPException(
            status_code=502,
            detail="Catalogue Service returned an error"
        )

    except httpx.RequestError:
        raise HTTPException(
            status_code=503,
            detail="Catalogue Service unavailable"
        )

    except ValueError:
        raise HTTPException(
            status_code=502,
            detail="Invalid response from Catalogue Service"
        )
