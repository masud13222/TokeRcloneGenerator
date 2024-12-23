import os
from pymongo import MongoClient

class Config:
    BOT_TOKEN = os.environ.get('BOT_TOKEN')
    if not BOT_TOKEN:
        raise ValueError("No BOT_TOKEN found in environment variables!")
        
    ADMIN_USERS = os.environ.get('ADMIN_USERS', '').split(',')
    API_ID = os.environ.get('API_ID')
    API_HASH = os.environ.get('API_HASH')
    LOG_CHANNEL = os.environ.get('LOG_CHANNEL')
    GOFILE_TOKEN = os.environ.get('GOFILE_TOKEN')
    AUTHORIZED_CHATS = []
    auth_chats = os.environ.get('AUTHORIZED_CHATS', '')
    if auth_chats:
        try:
            AUTHORIZED_CHATS = [int(x.strip()) for x in auth_chats.split(',') if x.strip()]
        except:
            print("Warning: Invalid AUTHORIZED_CHATS format")
    
    # Rclone default credentials
    RCLONE_CLIENT_ID = "202264815644.apps.googleusercontent.com"
    RCLONE_CLIENT_SECRET = "X4Z3ca8xfWDb1Voo-F9a7ZxJ"
    
    # MongoDB config
    MONGODB_URI = os.environ.get('MONGODB_URI')
    if not MONGODB_URI:
        raise ValueError("No MONGODB_URI found in environment variables!")
        
    DB_NAME = os.environ.get('DB_NAME', 'rclone_bot')
    
    # Concurrent settings
    MAX_CONCURRENT_TASKS = 10
    MAX_CONNECTIONS = 128
    TIMEOUT = 30
    
    @classmethod
    def get_db(cls):
        client = MongoClient(cls.MONGODB_URI)
        return client[cls.DB_NAME]