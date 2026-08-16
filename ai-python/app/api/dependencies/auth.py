from fastapi import Depends, Header, HTTPException

from app.core.config import Settings, get_settings


def verify_api_key(
    x_api_key: str | None = Header(None, alias="X-Api-Key"),
    settings: Settings = Depends(get_settings),
) -> None:
    if not x_api_key or x_api_key != settings.internal_api_key:
        raise HTTPException(status_code=401, detail="invalid internal api key")
