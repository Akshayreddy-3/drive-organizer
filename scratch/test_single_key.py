import os
from dotenv import load_dotenv
import google.generativeai as genai

load_dotenv()

# Test the single key fallback first
key = os.getenv("GEMINI_API_KEY")

if not key:
    print("❌ No GEMINI_API_KEY found in .env")
else:
    print(f"Testing key: {key[:10]}...{key[-4:]}")
    genai.configure(api_key=key)
    model = genai.GenerativeModel("gemini-1.5-flash")
    try:
        response = model.generate_content("Ping")
        print(f"✅ Success! Response: {response.text.strip()}")
    except Exception as e:
        print(f"❌ Failed: {e}")
