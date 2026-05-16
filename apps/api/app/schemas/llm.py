import re

from pydantic import BaseModel, Field, model_validator

from app.services.content_safety import contains_disallowed_term


class LLMOutput(BaseModel):
    model_config = {"extra": "forbid"}


class SimpleVocabExample(LLMOutput):
    token: str = Field(min_length=1, max_length=64)
    definition: str = Field(min_length=20, max_length=500)
    example: str = Field(min_length=10, max_length=500)

    @model_validator(mode="after")
    def _example_must_contain_token(self) -> "SimpleVocabExample":
        pattern = rf"\b{re.escape(self.token)}\b"
        if not re.search(pattern, self.example, flags=re.IGNORECASE):
            raise ValueError("example sentence must contain the target token")
        return self

    @model_validator(mode="after")
    def _no_disallowed_terms(self) -> "SimpleVocabExample":
        for field_name, value in (("definition", self.definition), ("example", self.example)):
            if contains_disallowed_term(value):
                raise ValueError(f"{field_name} contains a disallowed term")
        return self


class GeneratedVocabBatch(LLMOutput):
    items: list[SimpleVocabExample] = Field(min_length=1, max_length=20)
