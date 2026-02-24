from __future__ import annotations


def generate_text_response(prompt: str) -> str:
    cleaned = prompt.strip()
    if not cleaned:
        return "I need a prompt to generate a synchronized text, voice, and visual response."
    return (
        "OpenCommotion: "
        f"{cleaned}. I will explain this with concise narration and synchronized visuals."
    )
