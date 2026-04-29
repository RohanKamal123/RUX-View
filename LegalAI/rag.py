import openai

openai.api_key = "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"

user_query = "জমির নামজারি করতে হলে কী কী কাগজ লাগে?"

retrieved_texts = [
    "The Government may direct a survey of any land for the purpose of ascertaining boundaries or preparing maps.",
    "No person shall, except as provided, hold more than 33 acres of land.",
    "Documents related to land registration must be submitted to the local registrar office."
]

context = "\n\n".join(retrieved_texts)

prompt = f"""
আপনি একটি আইন সহকারী চ্যাটবট। ব্যবহারকারীর প্রশ্নের উত্তর শুধুমাত্র নিচের তথ্য ব্যবহার করে দিন এবং বাংলায় সহজভাবে ব্যাখ্যা করুন। 
প্রশ্ন: {user_query}

প্রাসঙ্গিক তথ্য:
{context}

উত্তর (Bengali) + সূত্র উল্লেখ করুন:
"""

# Chat-based API
response = openai.ChatCompletion.create(
    model="gpt-4o-mini",   # or "gpt-4o", "gpt-3.5-turbo"
    messages=[
        {"role": "system", "content": "You are a helpful legal assistant."},
        {"role": "user", "content": prompt}
    ],
    temperature=0.3,
    max_tokens=300
)

answer = response['choices'][0]['message']['content'].strip()
print("LegalAI Answer:\n", answer)
