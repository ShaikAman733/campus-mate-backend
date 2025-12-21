
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

# Keys will be loaded from Render settings

GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY")

MONGO_URI = os.environ.get("MONGO_URI")



genai.configure(api_key=GOOGLE_API_KEY)



app = Flask(__name__)

app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024



# Enable CORS for all domains

CORS(app, resources={r"/*": {"origins": "*"}}, methods=["GET", "POST", "DELETE", "OPTIONS"])



# --- DATABASE CONNECTION ---

client = MongoClient(MONGO_URI)

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

    file_data = data.get('file', None)



    print(f"\n🔍 Searching for: {user_message}")

    if file_data:

        print(f"📎 File attached: {file_data.get('name')}")



    prompt_parts = []

   

    if file_data and file_data.get('data'):

        try:

            base64_str = file_data['data']

            if "," in base64_str:

                base64_str = base64_str.split(",")[1]

           

            file_blob = {

                "mime_type": file_data.get('mime_type', 'image/png'),

                "data": base64_str

            }

            prompt_parts.append(file_blob)

        except Exception as e:

            print(f"File Error: {e}")



    if not user_message and file_data:

        user_message = "Analyze this image/document and tell me what it is about."



    context = deep_search(user_message)

   

    if context.strip() and not file_data:

        prompt_parts.append(f"""

        You are the CampusBot for RLJIT.

        Answer the user's question using ONLY the Source Data provided below.

       

        SOURCE DATA:

        {context}

       

        USER QUESTION: {user_message}

        """)

    else:

        prompt_parts.append(f"""

        You are the CampusBot for RLJIT.

       

        If a file is attached, analyze it carefully.

        If it's an image of a document, transcribe key details.

        If it's a campus photo, describe it.

       

        USER QUESTION: {user_message}

        """)



    try:

        model = genai.GenerativeModel("gemini-2.5-flash")

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

    try:

        items = list(db['lost_found'].find({}, {'image': 0}).sort('_id', -1).limit(50))

        for item in items:

            item['_id'] = str(item['_id'])

        return jsonify(items)

    except Exception as e:

        return jsonify({"error": str(e)}), 500



@app.route('/api/lostfound', methods=['POST'])

def add_lost_found():

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

    try:

        result = db['lost_found'].delete_one({'_id': ObjectId(id)})

        if result.deleted_count == 1:

            return jsonify({"message": "Item deleted"}), 200

        return jsonify({"error": "Item not found"}), 404

    except Exception as e:

        return jsonify({"error": str(e)}), 500



# ==========================================

#      🚀 AUTO-WAKE REDIRECT (UPDATED)

# ==========================================

@app.route('/', methods=['GET'])

def home():

    # This URL points to your Vercel Frontend

    frontend_url = "https://campus-mate-frontend.vercel.app"

   

    return f"""

    <!DOCTYPE html>

    <html>

        <head>

            <title>Waking up CampusBot...</title>

            <meta http-equiv="refresh" content="0; url={frontend_url}" />

            <style>

                body {{ font-family: sans-serif; text-align: center; padding-top: 50px; background-color: #1a1a1a; color: #fff; }}

                .loader {{ border: 5px solid #333; border-top: 5px solid #00d2ff; border-radius: 50%; width: 50px; height: 50px; animation: spin 1s linear infinite; margin: 20px auto; }}

                @keyframes spin {{ 0% {{ transform: rotate(0deg); }} 100% {{ transform: rotate(360deg); }} }}

            </style>

        </head>

        <body>

            <h1>🚀 Waking up the AI...</h1>

            <div class="loader"></div>

            <p>Please wait, redirecting you to CampusBot...</p>

            <script>

                // Fallback if meta refresh doesn't work

                window.location.href = "{frontend_url}";

            </script>

        </body>

    </html>

    """
if __name__ == '__main__':

    port = int(os.environ.get("PORT", 5001))

    app.run(host='0.0.0.0', port=port)