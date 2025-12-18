from dataclasses import dataclass


@dataclass
class ModelConfig:
    model_name: str
    temperature: float 
    max_tokens: int 