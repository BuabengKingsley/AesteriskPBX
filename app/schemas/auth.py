from pydantic import BaseModel, Field, model_validator


class AuthStartRequest(BaseModel):
    customer_reference: str | None = Field(None, min_length=3, max_length=32)
    phone_number: str | None = Field(None, min_length=7, max_length=24)

    @model_validator(mode="after")
    def exactly_one_identifier(self):
        if bool(self.customer_reference) == bool(self.phone_number):
            raise ValueError("Provide exactly one customer identifier")
        return self


class AuthStartResponse(BaseModel):
    challenge_id: str
    expires_in_seconds: int


class AuthVerifyRequest(BaseModel):
    challenge_id: str = Field(min_length=10, max_length=100)
    otp: str = Field(pattern=r"^\d{6}$")


class AuthVerifyResponse(BaseModel):
    session_token: str
    token_type: str = "bearer"
    expires_in_seconds: int

