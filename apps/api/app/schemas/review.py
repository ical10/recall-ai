from pydantic import BaseModel, Field


class ReviewState(BaseModel):
    ease_factor: float = Field(ge=1.3)
    interval_days: int = Field(ge=0)
    repetitions: int = Field(ge=0)


class ReviewUpdate(BaseModel):
    ease_factor: float = Field(ge=1.3)
    interval_days: int = Field(ge=0)
    repetitions: int = Field(ge=0)
