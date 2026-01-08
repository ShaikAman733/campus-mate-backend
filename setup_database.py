import json
import os
from pymongo import MongoClient


MONGO_URI = "mongodb+srv://shaikaman123:1234567890@cluster0.iocl6jk.mongodb.net/?appName=Cluster0&retryWrites=true&w=majority"
JSON_FILE_PATH = "alldata.json" 
def seed_database():
    try:
        # 1. Connect
        client = MongoClient(MONGO_URI)
        db = client['college_bot']
        collection = db['knowledge_base']
        
        # 2. CLEAR Old Data 
        print("🗑️  Clearing old data from MongoDB...")
        delete_result = collection.delete_many({})
        print(f"   Deleted {delete_result.deleted_count} old documents.")

        # 3. Load New JSON
        print(f"📂 Loading {JSON_FILE_PATH}...")
        with open(JSON_FILE_PATH, 'r', encoding='utf-8') as f:
            data = json.load(f)

        if isinstance(data, list):
            # 4. Insert New Data
            print(f"🚀 Uploading {len(data)} new records...")
            collection.insert_many(data)
            print("✅ Success! Database is now 100% clean and updated.")
        else:
            print("❌ Error: JSON file must contain a list of objects.")

    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    seed_database()