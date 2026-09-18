"""Cost calculation utilities — Phase 1.3 formula."""

_EST_OUTPUT_TOKENS = 500


def compute_cost(
    tokens_in: int,
    tokens_out: int,
    input_price_per_1k: float,
    output_price_per_1k: float,
) -> float:
    """Return USD cost: (tokens_in/1000 × input_price) + (tokens_out/1000 × output_price)."""
    return (tokens_in / 1000 * input_price_per_1k) + (tokens_out / 1000 * output_price_per_1k)


def estimate_cost(
    model: object,
    tokens_in: int,
    tokens_out: int | None = None,
) -> float:
    """Compute cost using actual or estimated token counts."""
    out = tokens_out if tokens_out is not None else _EST_OUTPUT_TOKENS
    return round(
        compute_cost(tokens_in, out, model.input_price_per_1k, model.output_price_per_1k),
        6,
    )


def cost_from_usage(
    model: object,
    usage: dict,
    estimated_input_tokens: int,
) -> float:
    """Prefer provider usage tokens; fall back to estimates when missing."""
    tokens_in = usage.get("prompt_tokens") or estimated_input_tokens
    tokens_out = usage.get("completion_tokens")
    if tokens_out is None:
        return estimate_cost(model, int(tokens_in))
    return round(
        compute_cost(
            int(tokens_in),
            int(tokens_out),
            model.input_price_per_1k,
            model.output_price_per_1k,
        ),
        6,
    )
