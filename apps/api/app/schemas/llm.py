from pydantic import BaseModel, Field, model_validator


class LLMOutput(BaseModel):
    model_config = {"extra": "forbid"}


class SimpleVocabExample(LLMOutput):
    token: str = Field(min_length=1, max_length=64)
    definition: str = Field(min_length=20, max_length=500)
    example: str = Field(min_length=10, max_length=500)

    @model_validator(mode="after")
    def _example_must_contain_token(self) -> "SimpleVocabExample":
        if self.token.lower() not in self.example.lower():
            raise ValueError("example sentence must contain the target token")
        return self
