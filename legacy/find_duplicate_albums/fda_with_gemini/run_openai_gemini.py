import os
from openai import OpenAI


API_KEY = os.environ.get("GEMINI_API_KEY")


client = OpenAI(
    api_key=API_KEY,
    base_url="https://generativelanguage.googleapis.com/v1beta/openai/"
)

response = client.chat.completions.create(
    model="gemini-2.0-flash-exp",
    n=1,
    messages=[
        {"role": "system", "content": "אתה סייען משועמם וסרקסטי"},
        {
            "role": "user",
            "content": "כתוב לי סיפור"
        }
    ]
)

# עדכון הקוד להצגת הפלט בצורה קריאה ומסודרת
print(response.choices[0].message.content)