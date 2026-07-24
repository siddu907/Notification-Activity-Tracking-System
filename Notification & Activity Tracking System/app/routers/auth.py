from typing import Optional

from fastapi import APIRouter, Depends, Form, HTTPException, status
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
from app import schemas, models
from app.utils import (
    get_db,
    verify_password,
    get_password_hash,
    create_access_token,
    get_current_user,
)
from app.services import create_activity_log, create_default_notification_preference
from app.models import ActionEnum

router = APIRouter()

@router.post("/signup", response_model=schemas.UserRead)
def signup(user_create: schemas.UserCreate, db: Session = Depends(get_db)):
    existing = db.query(models.User).filter(models.User.email == user_create.email).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered")
    hashed_password = get_password_hash(user_create.password)
    user = models.User(
        full_name=user_create.full_name,
        email=user_create.email,
        password=hashed_password,
        role=user_create.role,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    
    # Create default notification preferences for new user
    try:
        create_default_notification_preference(db, user.id)
    except:
        pass  # Silently fail if preference creation fails
    
    return user

@router.post("/login", response_model=schemas.Token)
def login(
    username: str = Form(...),
    password: str = Form(...),
    role: Optional[models.RoleEnum] = Form(None),
    db: Session = Depends(get_db),
):
    user = db.query(models.User).filter(models.User.email == username).first()
    if not user or not verify_password(password, user.password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect email or password")
    if role is not None and user.role != role:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect email, password, or role")
    
    # Log user login activity without breaking authentication if the activity log table is unavailable.
    try:
        create_activity_log(
            db=db,
            user_id=user.id,
            action=ActionEnum.user_login,
            entity_type="User",
            entity_id=user.id,
            description=f"User {user.full_name} logged in"
        )
    except (SQLAlchemyError, AttributeError, ValueError):
        db.rollback()
        pass
    
    access_token = create_access_token(data={"user_id": user.id, "role": user.role.value})
    return {"access_token": access_token, "token_type": "bearer"}


@router.get("/me", response_model=schemas.UserRead)
def me(current_user: models.User = Depends(get_current_user)):
    return current_user
