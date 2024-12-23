from datetime import datetime
from config import Config

class ErrorManager:
    def __init__(self):
        self.db = Config.get_db()
        self.errors = self.db.errors
        
    def log_error(self, user_id: int, error_type: str, error_message: str, task_info: dict = None):
        """Log error to database"""
        error_doc = {
            "user_id": user_id,
            "error_type": error_type,
            "error_message": str(error_message),
            "task_info": task_info,
            "timestamp": datetime.utcnow()
        }
        
        self.errors.insert_one(error_doc)
        return error_doc["_id"]
        
    def get_error(self, error_id):
        """Get error details by ID"""
        return self.errors.find_one({"_id": error_id})
        
    def get_short_error(self, error_message: str) -> str:
        """Get shortened version of error message"""
        if "Unable to rename file" in error_message:
            return "ফাইল রিনেম করতে সমস্যা হচ্ছে। কিছুক্ষণ পর আবার চেষ্টা করুন।"
        elif "The process cannot access the file" in error_message:
            return "ফাইল ব্যবহার করা যাচ্ছে না। কিছুক্ষণ পর আবার চেষ্টা করুন।"
        else:
            # Return first 100 characters of error
            return error_message[:100] + "..." if len(error_message) > 100 else error_message 