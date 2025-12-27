import os
from openai import OpenAI

def test_connection():
    # Check for API key
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        print("Error: OPENAI_API_KEY environment variable not found.")
        return

    print(f"OPENAI_API_KEY found: {api_key[:8]}...{api_key[-4:]}")

    try:
        client = OpenAI(api_key=api_key)
        
        print("Sending request to OpenAI...")
        completion = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "user", "content": "Say 'Connection successful!' if you can hear me."}
            ]
        )
        
        print("-" * 20)
        print("Response received:")
        print(completion.choices[0].message.content)
        print("-" * 20)
        print("\nSUCCESS: OpenAI API connection verified.")

    except Exception as e:
        print(f"\nERROR: Failed to connect to OpenAI API.\n{e}")

if __name__ == "__main__":
    test_connection()
