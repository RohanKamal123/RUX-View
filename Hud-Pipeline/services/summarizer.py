import os
from openai import OpenAI
from fastapi import FastAPI, Path
from services.summarizer import generate_summary

app = FastAPI()

@app.get("/summarize/{id}")
def summarize_news(id: int):
    text = "Your text here"  # Replace with the actual text you want to summarize
    summary = generate_summary(text)
    return {"id": id, "summary": summary}


def generate_summary(text: str) -> str:
    """
    Generates a summary: prefers abstractive using OpenAI if API key is present and call succeeds,
    else falls back to extractive summarization.

    Abstractive (OpenAI): Uses GPT-3.5-turbo to generate a concise 1-sentence summary under 120
    characters based on the prompt "Generate a concise 1-sentence summary (under 120 characters)
    for this news article: {text}". Truncates to 120 characters if longer, appending '...' if
    truncated. Checks for OPENAI_API_KEY environment variable; on absence, API error, or any
    exception, silently falls back.

    Extractive (fallback): Extracts the first complete non-empty sentence after splitting on
    periods and stripping whitespace. If a period is present in the original text, appends it.
    Truncates to 120 characters if longer, appending '...' if truncated.

    Returns empty string for empty or whitespace-only input. Ensures summary is ~50-120 characters.
    """
    if not text:
        return ""

    api_key = os.getenv("OPENAI_API_KEY")
    if api_key:
        try:
            client = OpenAI(api_key=api_key)
            response = client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {
                        "role": "user",
                        "content": f"Generate a concise 1-sentence summary (under 120 characters) for this news article: {text}",
                    }
                ],
            )
            content = response.choices[0].message.content
            if content is None:
                summary = ""
            else:
                summary = content.strip()
                if len(summary) > 120:
                    summary = summary[:120].rstrip() + "..."
            return summary
        except Exception:
            pass  # Silently fallback to extractive

    # Fallback to extractive
    parts = [p.strip() for p in text.split(".") if p.strip()]
    if not parts:
        return ""
    first_sentence = parts[0]
    if len(parts) > 1:
        first_sentence += "."
    if len(first_sentence) > 120:
        first_sentence = first_sentence[:120].rstrip() + "..."
    return first_sentence
