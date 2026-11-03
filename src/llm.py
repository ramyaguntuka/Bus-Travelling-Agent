"""Shared Groq chat model used for summary memory and itinerary prose."""

# Groq no longer serves llama-3.3-70b-versatile. This is the current general chat model.
GROQ_MODEL = "openai/gpt-oss-120b"


def make_chat(api_key: str, temperature: float):
    from langchain_groq import ChatGroq

    return ChatGroq(
        model=GROQ_MODEL,
        temperature=temperature,
        api_key=api_key,
        max_retries=1,
    )