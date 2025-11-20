from google import genai
from google.genai import types

# API_KEY = userdata.get('GOOGLE_API_KEY')
API_KEY = "AIzaSyBa3kG9Sc2On_DeaMGENdDR9rglISWSfUo"

client = genai.Client(api_key=API_KEY)
chat = client.chats.create(
    model="gemini-2.5-flash",
    config=types.GenerateContentConfig(
        system_instruction="Write in poem style/structure.",
        thinking_config=types.ThinkingConfig(thinking_budget=0)
    ),
)

response = chat.send_message("I have 2 dogs in my house.")
print(response.text)

response = chat.send_message("How many paws are in my house?")
print(response.text)

# for message in chat.get_history():
#     print(f'role - {message.role}',end=": ")
#     print(message.parts[0].text)



