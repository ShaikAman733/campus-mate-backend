# backend/check_db.py
from pymongo import MongoClient

MONGO_URI = "mongodb+srv://shaikaman123:1234567890@cluster0.iocl6jk.mongodb.net/?appName=Cluster0&retryWrites=true&w=majority"
client = MongoClient(MONGO_URI)
db = client['college_bot']
collection = db['lost_found']

count = collection.count_documents({})
print(f"\n📊 Total Items in DB: {count}")

items = list(collection.find({}, {'image': 0}).limit(5)) # Check first 5, exclude images
for item in items:
    print(f" - Found: {item.get('item')} ({item.get('type')})")