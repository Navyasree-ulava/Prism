from pydantic import BaseModel


class ModelOut(BaseModel):
    id: str
    provider: str
    capabilities: list[str]
    context_window: int
    quality_score: float
    input_price_per_1k: float
    output_price_per_1k: float
    avg_latency_ms: int
    enabled: bool

    model_config = {"from_attributes": True}
