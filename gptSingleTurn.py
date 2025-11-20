from openai import OpenAI

# Hardcoded API key
API_KEY = "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"

client = OpenAI(api_key=API_KEY)

def main():
    try:
        response = client.chat.completions.create(
            model="gpt-4.1-mini",
            messages=[
                {"role": "user", "content": "Say hello"}
            ]
        )
        print("Response:")
        print(response.choices[0].message["content"])
    except Exception as e:
        print("Error:", e)

if __name__ == "__main__":
    main()
