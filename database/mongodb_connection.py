from pymongo import MongoClient
from dotenv import load_dotenv
import os

load_dotenv()

def get_mongodb_connection():
    """Create and return a MongoDB connection."""
    try:
        client = MongoClient('mongodb://localhost:27017/')
        db = client['academicworld']  
        
        print("\nMongoDB Connection Details:")
        print(f"Database: {db.name}")
        print(f"Available collections: {db.list_collection_names()}")
        
        if 'publications' in db.list_collection_names():
            count = db.publications.count_documents({})
            print(f"Number of documents in publications collection: {count}")
        
        return db
    except Exception as e:
        print(f"Error connecting to MongoDB: {e}")
        return None 