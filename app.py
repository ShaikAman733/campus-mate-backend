import os
import json
import io
import base64
from datetime import datetime
from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
from pymongo import MongoClient
from bson.objectid import ObjectId
import google.generativeai as genai

app = Flask(__name__)
CORS(app)

# --- CONFIGURATION ---
API_KEYS_STR = os.environ.get("GOOGLE_API_KEYS", "")
API_KEYS = [k.strip() for k in API_KEYS_STR.split(",") if k.strip()]
MONGO_URI = os.environ.get("MONGO_URI")

# --- DATABASE CONNECTION ---
client = MongoClient(MONGO_URI)
db = client['college_bot']
KNOWLEDGE_BASE = []

def reload_kb_data():
    global KNOWLEDGE_BASE
    try:
        collection = db['knowledge_base']
        KNOWLEDGE_BASE = list(collection.find({}))
        print(f"✅ DB: Loaded {len(KNOWLEDGE_BASE)} records.")
        return True
    except Exception as e:
        print(f"❌ DB Load Error: {e}")
        return False

reload_kb_data()

# Helper to mask keys in the console for security
def mask_key(key):
    return f"{key[:4]}...{key[-4:]}" if len(key) > 8 else "****"

# ==========================================
# 🔄 API KEY ROTATION WITH CONSOLE LOGS
# ==========================================

def generate_content_with_fallback(prompt_parts):
    """Loops through API keys and prints status to the console."""
    last_error = None
    
    for index, key in enumerate(API_KEYS):
        masked = mask_key(key)
        print(f"🚀 [ATTEMPT {index + 1}] Using API Key: {masked}")
        
        try:
            genai.configure(api_key=key)
            model = genai.GenerativeModel("gemini-2.5-flash") 
            
            response = model.generate_content(prompt_parts)
            
            print(f"✅ [SUCCESS] Response received with Key #{index + 1} ({masked})")
            return response.text
            
        except Exception as e:
            error_msg = str(e).lower()
            last_error = e
            
            # Identify rate limit / quota errors
            if any(x in error_msg for x in ["429", "quota", "limit"]):
                print(f"⚠️ [EXHAUSTED] Key #{index + 1} hit its limit. Switching...")
                continue 
            else:
                print(f"❌ [API ERROR] Critical issue with Key #{index + 1}: {e}")
                break

    raise Exception(f"All keys failed. Last error: {last_error}")

# ==========================================
# 🤖 CHATBOT ROUTE
# ==========================================

@app.route('/chat', methods=['POST'])
def chat():
    data = request.get_json()
    user_message = data.get('message', '')
    file_data = data.get('file', None) 

    # Prepare prompt parts
    prompt_parts = []
    if file_data and file_data.get('data'):
        try:
            base64_str = file_data['data'].split(",")[1] if "," in file_data['data'] else file_data['data']
            prompt_parts.append({"mime_type": file_data.get('mime_type', 'image/png'), "data": base64_str})
        except Exception as e:
            print(f"File Error: {e}")

    # Your context search logic (simplified here for brevity)
    system_instruction = "You are the CampusBot for RLJIT."
    prompt_parts.append(f"{system_instruction}\n\nUSER QUESTION: {user_message}")

    try:
        # Calls the rotation logic with console feedback
        ai_response = generate_content_with_fallback(prompt_parts)
        return jsonify({"response": ai_response})
    except Exception as e:
        print(f"🛑 [FINAL FAILURE] {e}")
        return jsonify({"error": "All AI keys are busy. Try again later."}), 503

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5001))
    app.run(host='0.0.0.0', port=port)