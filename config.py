import os
from pymongo import MongoClient

class Config:
    API_ID = "17462098"
    API_HASH = "149b3719dc136ddd05624dc69190dffd"
    BOT_TOKEN = "7963788326:AAH_MhtEld_qyqLF4zXlS1tZP6uGnYl4oe4"
    
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