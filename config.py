import os
from pymongo import MongoClient

class Config:
    # Get from environment variables
    API_ID = os.environ.get("API_ID")
    API_HASH = os.environ.get("API_HASH")
    BOT_TOKEN = os.environ.get("BOT_TOKEN")
    
    # Default Rclone configs
    RCLONE_CLIENT_ID = "202264815644.apps.googleusercontent.com"
    RCLONE_CLIENT_SECRET = "X4Z3ca8xfWDb1Voo-F9a7ZxJ"
    
    # MongoDB - Optional
    USE_MONGODB = False
    MONGO_URL = "mongodb://localhost:27017"
    
    @staticmethod
    def get_db():
        if Config.USE_MONGODB:
            client = MongoClient(Config.MONGO_URL)
            return client.gdrive_bot
        return None 