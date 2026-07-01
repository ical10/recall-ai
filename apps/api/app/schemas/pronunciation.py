from __future__ import annotations

from pydantic import BaseModel, Field, model_validator

from app.services.content_safety import contains_disallowed_term


class PronunciationVerdict(BaseModel):
    said_target: bool
    heard: str
    confidence: float = Field(ge=0, le=1)
    feedback: str = Field(max_length=200)

    @model_validator(mode="after")
    def _require_feedback_when_wrong(self) -> PronunciationVerdict:
        if not self.said_target and not self.feedback.strip():
            raise ValueError("feedback required when said_target is false")
        return self

    @model_validator(mode="after")
    def _disallowed_terms(self) -> PronunciationVerdict:
        if contains_disallowed_term(self.heard):
            raise ValueError("heard contains disallowed term")
        if contains_disallowed_term(self.feedback):
            raise ValueError("feedback contains disallowed term")
        return self
