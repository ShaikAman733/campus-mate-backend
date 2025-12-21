import os
from dotenv import load_dotenv 
load_dotenv() 
import json
import io
import base64
import random
from datetime import datetime
from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
from pymongo import MongoClient
from bson.objectid import ObjectId
import google.generativeai as genai

# --- CONFIGURATION ---
API_KEYS_STRING = os.environ.get("GOOGLE_API_KEYS") or os.environ.get("GOOGLE_API_KEY", "")
MONGO_URI = os.environ.get("MONGO_URI")

API_KEYS = [k.strip() for k in API_KEYS_STRING.split(",") if k.strip()]

class KeyRotator:
    def __init__(self, keys):
        self.keys = keys
        self.current_index = 0
        print(f"📡 Initialized KeyRotator with {len(self.keys)} keys.")

    def get_key(self):
        if not self.keys:
            return None
        return self.keys[self.current_index]

    def get_key_number(self):
        """Returns a human-readable key number (1, 2, 3...)"""
        return self.current_index + 1

    def rotate(self):
        if len(self.keys) > 1:
            self.current_index = (self.current_index + 1) % len(self.keys)
            print(f"🔄 ROTATION: Switched to Key {self.get_key_number()}")
        return self.get_key()

rotator = KeyRotator(API_KEYS)

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024
CORS(app, resources={r"/*": {"origins": "*"}}, methods=["GET", "POST", "DELETE", "OPTIONS"])

# --- DATABASE CONNECTION ---
print("🔗 Connecting to MongoDB...")
client = MongoClient(MONGO_URI)
db = client['college_bot']
KNOWLEDGE_BASE = []

def reload_kb_data():
    global KNOWLEDGE_BASE
    try:
        collection = db['knowledge_base']
        KNOWLEDGE_BASE = list(collection.find({}))
        print(f"✅ KB RELOAD: Successfully loaded {len(KNOWLEDGE_BASE)} records.")
        return True
    except Exception as e:
        print(f"❌ KB RELOAD ERROR: {e}")
        return False

reload_kb_data()

def deep_search(query):
    if not KNOWLEDGE_BASE: 
        print("⚠️ SEARCH: Knowledge base is empty.")
        return ""
    
    keywords = [w.lower() for w in query.split() if len(w) > 2]
    if not keywords: return ""
    
    scored_results = []
    for doc in KNOWLEDGE_BASE:
        score = 0
        doc_str = str(doc).lower()
        title = doc.get('title', '').lower()
        for k in keywords:
            if k in doc_str: score += 1
            if k in title: score += 5
        if score > 0: scored_results.append((score, doc))
    
    scored_results.sort(key=lambda x: x[0], reverse=True)
    top_docs = [item[1] for item in scored_results[:5]]
    
    context_text = ""
    for i, doc in enumerate(top_docs):
        context_text += f"--- SOURCE {i+1} ---\nTitle: {doc.get('title', 'N/A')}\nDetails: {json.dumps(doc.get('details', {}))}\nSummary: {doc.get('text_for_ai', '')}\n\n"
    return context_text

# --- CHATBOT ROUTES ---

@app.route('/chat', methods=['POST'])
def chat():
    data = request.get_json()
    user_message = data.get('message', '')
    file_data = data.get('file', None)
    history = data.get('history', [])
    user_name = data.get('userName', 'Student')

    # Re-initialize context search
    context = deep_search(user_message)
    
    # FIX 1: Explicitly tell the AI it is Multimodal
    system_instruction = (
        f"You are CampusBot for RLJIT. You are talking to {user_name}. "
        "You CAN see and analyze images, photos, and PDF documents. "
        f"Context from RLJIT records: {context}"
    )

    # FIX 2: Correctly format parts for Gemini 1.5/2.5
    prompt_parts = []
    
    if file_data and file_data.get('data'):
        try:
            base64_str = file_data['data']
            if "," in base64_str:
                base64_str = base64_str.split(",")[1]
            
            # Map common types if mime_type is missing
            mime = file_data.get('mime_type', 'image/png')
            
            prompt_parts.append({
                "mime_type": mime, 
                "data": base64_str
            })
            print(f"📁 Processing {mime} file...")
        except Exception as e:
            print(f"❌ Backend File Error: {e}")

    # Always add the text part
    prompt_parts.append(user_message if user_message else "Analyze this file.")

    max_retries = len(API_KEYS)
    for attempt in range(max_retries):
        current_key = rotator.get_key()
        try:
            genai.configure(api_key=current_key)
            # Using Flash-Lite for higher RPM limits
            model = genai.GenerativeModel(
                model_name="gemini-2.5-flash", 
                system_instruction=system_instruction
            )
            
            # Start chat with context history
            chat_session = model.start_chat(history=history)
            response = chat_session.send_message(prompt_parts)
            
            return jsonify({"response": response.text})
        except Exception as e:
            print(f"🔄 ROTATION: {e}")
            rotator.rotate()
    
    return jsonify({"error": "Failed after exhaustion"}), 500
if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5001))
    print(f"🚀 Python Service running on port {port}")
    app.run(host='0.0.0.0', port=port)