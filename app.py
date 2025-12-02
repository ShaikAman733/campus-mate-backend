import os
import json
import io
import base64
from datetime import datetime
from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
from pymongo import MongoClient
from bson.objectid import ObjectId
from bson.errors import InvalidId
import google.generativeai as genai

# --- CONFIGURATION ---
# Ensure your API Key is correct
# Keys will be loaded from Render settings, not code
GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY")
MONGO_URI = os.environ.get("MONGO_URI")

genai.configure(api_key=GOOGLE_API_KEY)

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024 

# Enable CORS for all domains
CORS(app, resources={r"/*": {"origins": "*"}}, methods=["GET", "POST", "DELETE", "OPTIONS"])

# --- DATABASE CONNECTION ---
client = MongoClient(MONGO_URI)
# NOTE: Chatbot data lives in 'college_bot'. Users live in 'campus-mate-db' (managed by Node.js)
db = client['college_bot']

# Global variable to cache chatbot knowledge
KNOWLEDGE_BASE = []

def reload_kb_data():
    """Fetches ALL data from MongoDB into memory for deep searching."""
    global KNOWLEDGE_BASE
    try:
        collection = db['knowledge_base']
        cursor = collection.find({})
        KNOWLEDGE_BASE = list(cursor)
        print(f"✅ Loaded {len(KNOWLEDGE_BASE)} records into memory.")
        return True
    except Exception as e:
        print(f"❌ DB Load Error: {e}")
        KNOWLEDGE_BASE = []
        return False

# Load chatbot data on startup
reload_kb_data()

# --- HELPER: Deep Search ---
def deep_search(query):
    if not KNOWLEDGE_BASE: return ""
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

# ==========================================
#      🤖 CHATBOT ROUTES
# ==========================================

@app.route('/reload', methods=['POST'])
def reload_data():
    """Endpoint to force reload knowledge base without restarting server"""
    success = reload_kb_data()
    if success:
        return jsonify({"message": "Knowledge base reloaded successfully", "count": len(KNOWLEDGE_BASE)}), 200
    return jsonify({"error": "Failed to reload data"}), 500

@app.route('/chat', methods=['POST'])
def chat():
    data = request.get_json()
    user_message = data.get('message', '')
    file_data = data.get('file', None) # Get file data if exists

    print(f"\n🔍 Searching for: {user_message}")
    if file_data:
        print(f"📎 File attached: {file_data.get('name')}")

    # --- 1. Prepare Prompt Content ---
    prompt_parts = []
    
    # If file exists, process it for Gemini
    if file_data and file_data.get('data'):
        try:
            # Remove "data:image/png;base64," prefix if present
            base64_str = file_data['data']
            if "," in base64_str:
                base64_str = base64_str.split(",")[1]
            
            # Create Gemini Blob
            file_blob = {
                "mime_type": file_data.get('mime_type', 'image/png'),
                "data": base64_str
            }
            prompt_parts.append(file_blob)
        except Exception as e:
            print(f"File Error: {e}")

    # --- 2. Determine Text Prompt ---
    
    # If just a file with no text, ask for summary
    if not user_message and file_data:
        user_message = "Analyze this image/document and tell me what it is about."

    context = deep_search(user_message)
    
    # Construct System Instructions
    if context.strip() and not file_data:
        # Standard RAG (Text Only)
        prompt_parts.append(f"""
        You are the CampusBot for RLJIT. 
        Answer the user's question using ONLY the Source Data provided below. 
        
        SOURCE DATA:
        {context}
        
        USER QUESTION: {user_message}
        """)
    else:
        # General AI Mode (or File Analysis Mode)
        prompt_parts.append(f"""
        You are the CampusBot for RLJIT.
        
        If a file is attached, analyze it carefully. 
        If it's an image of a document, transcribe key details.
        If it's a campus photo, describe it.
        
        USER QUESTION: {user_message}
        """)

    try:
        # Using 1.5-flash as it supports Multimodal inputs (Images/PDFs)
        model = genai.GenerativeModel("gemini-2.5-flash")
        
        # Pass list of [Text, ImageBlob]
        response = model.generate_content(prompt_parts)
        return jsonify({"response": response.text})
    except Exception as e:
        print(f"❌ Gemini Error: {e}")
        return jsonify({"error": str(e)}), 500

# ==========================================
#      🆕 LOST AND FOUND INTEGRATION
# ==========================================

@app.route('/api/lostfound/image/<id>', methods=['GET'])
def get_item_image(id):
    """Serve the image file for a specific item ID."""
    try:
        item = db['lost_found'].find_one({'_id': ObjectId(id)})
        if not item or not item.get('image'):
            return "Image not found", 404

        header, encoded = item['image'].split(',', 1)
        mime_type = header.split(':')[1].split(';')[0]
        binary_data = base64.b64decode(encoded)
        return send_file(io.BytesIO(binary_data), mimetype=mime_type)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/lostfound', methods=['GET'])
def get_lost_found():
    """Fetch all items (Excluding Image Data for Speed)."""
    try:
        items = list(db['lost_found'].find({}, {'image': 0}).sort('_id', -1).limit(50))
        for item in items:
            item['_id'] = str(item['_id'])
        return jsonify(items)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/lostfound', methods=['POST'])
def add_lost_found():
    """Add a new item."""
    try:
        data = request.get_json()
        new_item = {
            "type": data.get('type', 'lost'),
            "item": data.get('item'),
            "location": data.get('location'),
            "description": data.get('description'),
            "contact": data.get('contact'),
            "image": data.get('image'),
            "time": datetime.now().strftime("%d %b, %I:%M %p") 
        }
        result = db['lost_found'].insert_one(new_item)
        new_item['_id'] = str(result.inserted_id)
        return jsonify(new_item), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/lostfound/<id>', methods=['DELETE'])
def delete_lost_found(id):
    """Delete an item by ID."""
    try:
        result = db['lost_found'].delete_one({'_id': ObjectId(id)})
        if result.deleted_count == 1:
            return jsonify({"message": "Item deleted"}), 200
        return jsonify({"error": "Item not found"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ==========================================
#      HEALTH CHECK
# ==========================================
@app.route('/', methods=['GET'])
def home():
    return jsonify({"status": "Online", "message": "Python AI Server is Running on Port 5001"}), 200

if __name__ == '__main__':
    # Run on port 5001 to avoid conflict with Node (5000)
    app.run(debug=True, port=5001)