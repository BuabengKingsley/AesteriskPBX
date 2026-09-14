from typing import Annotated

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.database.session import get_db
from app.models import Customer
from app.services.authentication_service import authenticate_session, authenticate_token

bearer = HTTPBearer(auto_error=True)


def current_customer(credentials: Annotated[HTTPAuthorizationCredentials, Depends(bearer)],
                     db: Annotated[Session, Depends(get_db)], settings: Annotated[Settings, Depends(get_settings)]) -> Customer:
    return authenticate_token(db, credentials.credentials, settings)


def current_elevated_customer(credentials: Annotated[HTTPAuthorizationCredentials, Depends(bearer)],
                              db: Annotated[Session, Depends(get_db)], settings: Annotated[Settings, Depends(get_settings)]) -> Customer:
    session = authenticate_session(db, credentials.credentials, settings)
    customer = db.get(Customer, session.customer_id)
    if not customer or customer.status != "active":
        raise HTTPException(status_code=401, detail="Invalid session")
    if session.authentication_level != "elevated":
        raise HTTPException(status_code=403, detail="Elevated authentication required for this action")
    return customer

