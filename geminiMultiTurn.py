import os
from google import genai
import ollama

client = genai.Client(api_key="")



chat = client.chats.create(
    model="gemini-2.5-flash"
    )
gemini_chat = client.chats.create(
    model="gemini-2.5-flash",
    history=[]
)
llama_history = []

def ask_gemini(text):
    response = gemini_chat.send_message(text)
    return response.text

def ask_llama(text):
    llama_history.append({'role': 'user', 'content': text})
    
    response = ollama.chat(model='gpt-oss:120b-cloud', messages=llama_history)
    
    reply = response['message']['content']
    llama_history.append({'role': 'assistant', 'content': reply})
    return reply

# # 4. 发送消息
# response = chat.send_message("I have 2 dogs in my house.")
# print("User: I have 2 dogs in my house.")
# print(f"Gemini: \n{response.text}")
# print("-" * 20)

# response = chat.send_message("How many paws are in my house?")
# print("User: How many paws are in my house?")
# print(f"Gemini: \n{response.text}")

# 5. 查看历史记录 (可选)
# print("\n--- History ---")
# for message in chat.history:
#     print(f'Role: {message.role}, Content: {message.parts[0].text}')

topic = "Let's negotitate a trade in Monopoly, now is your turn, you can request a deal for properties or cash from the other user remember you only have one round negotiation, if the other counter, you can only accept or reject."
print("User:", topic)
current_speaker = "Gemini"
last_message = topic
ROUNDS = 1
print("-" * 20)
print("Gemini thinking...")
reply = ask_gemini(last_message)
print(f"Gemini: {reply}")
last_message = reply
print("-" * 20)
print("Llama thinking...")
topic2 = "It's your turn to respond to the trade proposal in Monopoly, you can accept, reject or counter the offer, you can only counter once."
reply = ask_llama(topic2 + last_message)
print(f"Llama: {reply}")
last_message = reply
current_speaker = "Gemini"
print("-" * 20)
print("Conversation ended.")