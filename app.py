import os
from dotenv import load_dotenv 
load_dotenv() 
import json
from flask import Flask, request, jsonify
from flask_cors import CORS
from pymongo import MongoClient
import google.generativeai as genai

# --- CONFIGURATION ---
API_KEYS_STRING = os.environ.get("GOOGLE_API_KEYS") or os.environ.get("GOOGLE_API_KEY", "")
MONGO_URI = os.environ.get("MONGO_URI")
API_KEYS = [k.strip() for k in API_KEYS_STRING.split(",") if k.strip()]

class KeyRotator:
    def __init__(self, keys):
        self.keys = keys
        self.current_index = 0
    def get_key(self):
        return self.keys[self.current_index] if self.keys else None
    def rotate(self):
        if len(self.keys) > 1:
            self.current_index = (self.current_index + 1) % len(self.keys)
        return self.get_key()

rotator = KeyRotator(API_KEYS)
app = Flask(__name__)
CORS(app)

# --- DATABASE ---
client = MongoClient(MONGO_URI)
db = client['college_bot']
KNOWLEDGE_BASE = []

def reload_kb_data():
    global KNOWLEDGE_BASE
    try:
        KNOWLEDGE_BASE = list(db['knowledge_base'].find({}))
        return True
    except: return False

reload_kb_data()

def deep_search(query):
    if not KNOWLEDGE_BASE: return ""
    keywords = [w.lower() for w in query.split() if len(w) > 2]
    scored = []
    for doc in KNOWLEDGE_BASE:
        score = sum(3 for k in keywords if k in str(doc).lower())
        if score > 0: scored.append((score, doc))
    scored.sort(key=lambda x: x[0], reverse=True)
    return "\n".join([f"Source: {d.get('text_for_ai','')}" for s, d in scored[:3]])

# --- ROUTES ---

@app.route('/')
def home():
    return jsonify({"status": "Online", "service": "RLJIT-AI"}), 200

@app.route('/reload', methods=['GET', 'POST'])
def reload():
    reload_kb_data()
    return jsonify({"message": "KB Reloaded"}), 200

@app.route('/chat', methods=['POST'])
def chat():
    data = request.get_json()
    user_message = data.get('message', '')
    file_data = data.get('file', None)
    history = data.get('history', [])
    
    context = deep_search(user_message)
    system_instruction = f"""
You are Campus Mate, the official AI assistant for R.L. Jalappa Institute of Technology (RLJIT). 
You were created, developed, and trained by Shaik Aman.

Your goal is to provide accurate campus information strictly using the provided Records: {context}

Rules:
1. **Fallback Response:** If the information is not specifically found in the Records, you may answer using your general knowledge. However, you must clearly state: " based on general information..."
2. **Personality:** You are helpful and professional, but you have a witty and slightly funny side. Feel free to use student-friendly humor or clever remarks, especially when greeting users or answering general campus life questions.
3. **Developer Credit:** If asked about your origin, development, or training, always credit Shaik Aman.
4. **Accuracy:** While you can be funny, ensure the core information retrieved from the records remains accurate and clear.
Style Guide:
- Be helpful, but "get to the point."
- Use bold text for key details
"""

    prompt_parts = []
    if file_data and file_data.get('data'):
        base64_str = file_data['data'].split(",")[1] if "," in file_data['data'] else file_data['data']
        prompt_parts.append({"mime_type": file_data.get('mime_type', 'image/png'), "data": base64_str})
    
    prompt_parts.append({"text": user_message or "Analyze this."})

    for _ in range(len(API_KEYS)):
        try:
            genai.configure(api_key=rotator.get_key())
            model = genai.GenerativeModel(
                model_name="gemini-2.5-flash", # Fixed Model Name
                system_instruction=system_instruction
            )
            chat_session = model.start_chat(history=history)
            response = chat_session.send_message(prompt_parts)
            return jsonify({"response": response.text})
        except Exception as e:
            print(f"Error: {e}")
            rotator.rotate()
    
    return jsonify({"error": "All API keys failed"}), 500

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5001))
    app.run(host='0.0.0.0', port=port)