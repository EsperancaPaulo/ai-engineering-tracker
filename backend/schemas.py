from datetime import datetime
from pydantic import BaseModel, ConfigDict, EmailStr, Field, SecretStr, field_validator


def normalize_email(value: str) -> str:
    return value.strip().lower()


class Registration(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=100)
    email: EmailStr = Field(max_length=255)
    password: SecretStr = Field(min_length=15, max_length=128)

    @field_validator("name", mode="before")
    @classmethod
    def clean_name(cls, value):
        return value.strip() if isinstance(value, str) else value

    @field_validator("email", mode="before")
    @classmethod
    def clean_email(cls, value):
        return normalize_email(value) if isinstance(value, str) else value


class PublicUser(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    email: EmailStr
    role: str
    created_at: datetime


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
