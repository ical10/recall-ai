from pydantic import BaseModel, ConfigDict, Field


class ReviewState(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    ease_factor: float = Field(ge=1.3)
    interval_days: int = Field(ge=0)
    repetitions: int = Field(ge=0)


# SM-2 input (current state) and output (next state) are structurally identical;
# ReviewUpdate names the output role at call sites.
ReviewUpdate = ReviewState
