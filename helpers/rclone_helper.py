import os
import json
import time
from datetime import datetime
from config import Config
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
import socket
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

class RcloneManager:
    def __init__(self):
        self.db = Config.get_db()
        self.users = self.db.users
        self.SCOPES = ['https://www.googleapis.com/auth/drive']
        
    def _find_available_port(self):
        """Find an available port"""
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(('', 0))
            s.listen(1)
            port = s.getsockname()[1]
        return port
        
    def get_auth_url(self, user_id: int, use_default: bool = False):
        """Generate authorization URL for Google Drive"""
        redirect_uri = "http://127.0.0.1:53682"
        
        auth_url = (
            "https://accounts.google.com/o/oauth2/auth"
            f"?client_id={Config.RCLONE_CLIENT_ID}"
            f"&redirect_uri={redirect_uri}"
            "&response_type=code"
            "&scope=https://www.googleapis.com/auth/drive"
            "&access_type=offline"
            "&approval_prompt=force"
        )
        
        # Store config for later use
        self.users.update_one(
            {"user_id": user_id},
            {
                "$set": {
                    "oauth_config": {
                        "client_id": Config.RCLONE_CLIENT_ID,
                        "client_secret": Config.RCLONE_CLIENT_SECRET,
                        "redirect_uri": redirect_uri
                    },
                    "created_at": datetime.utcnow()
                }
            },
            upsert=True
        )
        
        return auth_url
        
    async def save_token(self, user_id: int, code: str):
        """Save token after authorization"""
        try:
            user = self.users.find_one({"user_id": user_id})
            if not user or "oauth_config" not in user:
                raise Exception("No pending authorization found")
                
            oauth_config = user["oauth_config"]
            
            # Create flow with same redirect_uri that was used for auth URL
            flow = InstalledAppFlow.from_client_config(
                {
                    "installed": {
                        "client_id": Config.RCLONE_CLIENT_ID,
                        "client_secret": Config.RCLONE_CLIENT_SECRET,
                        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                        "token_uri": "https://oauth2.googleapis.com/token",
                        "redirect_uris": ["http://127.0.0.1:53682"]
                    }
                },
                self.SCOPES
            )
            
            # Set redirect_uri
            flow.redirect_uri = "http://127.0.0.1:53682"
            
            # Fetch token
            token = flow.fetch_token(code=code)
            credentials = flow.credentials
            
            token_data = {
                "token": credentials.token,
                "refresh_token": credentials.refresh_token,
                "token_uri": credentials.token_uri,
                "client_id": credentials.client_id,
                "client_secret": credentials.client_secret,
                "scopes": credentials.scopes,
                "expiry": credentials.expiry.isoformat()
            }
            
            self.users.update_one(
                {"user_id": user_id},
                {
                    "$set": {
                        "token": token_data,
                        "updated_at": datetime.utcnow()
                    },
                    "$unset": {"oauth_config": ""}
                }
            )
            
            return True
            
        except Exception as e:
            raise Exception(f"Failed to save token: {str(e)}")
        
    def check_token(self, user_id: int) -> bool:
        """Check if user has valid token"""
        try:
            user = self.users.find_one({"user_id": user_id})
            if not user or "token" not in user:
                return False
                
            token_data = user["token"]
            credentials = Credentials(
                token=token_data["token"],
                refresh_token=token_data["refresh_token"],
                token_uri=token_data["token_uri"],
                client_id=token_data["client_id"],
                client_secret=token_data["client_secret"],
                scopes=token_data["scopes"]
            )
            
            if credentials.expired:
                try:
                    credentials.refresh(Request())
                    # Update token in database
                    token_data = {
                        "token": credentials.token,
                        "refresh_token": credentials.refresh_token,
                        "token_uri": credentials.token_uri,
                        "client_id": credentials.client_id,
                        "client_secret": credentials.client_secret,
                        "scopes": credentials.scopes,
                        "expiry": credentials.expiry.isoformat()
                    }
                    self.users.update_one(
                        {"user_id": user_id},
                        {"$set": {"token": token_data}}
                    )
                    return True
                except:
                    return False
                    
            return True
        except:
            return False
        
    async def upload_file(self, file_path: str, filename: str, status_message, user_id: int, username: str):
        """Upload file to Google Drive"""
        try:
            user = self.users.find_one({"user_id": user_id})
            if not user or "token" not in user:
                raise Exception("No valid token found")
            
            token_data = user["token"]
            credentials = Credentials(
                token=token_data["token"],
                refresh_token=token_data["refresh_token"],
                token_uri=token_data["token_uri"],
                client_id=token_data["client_id"],
                client_secret=token_data["client_secret"],
                scopes=token_data["scopes"]
            )
            
            # Upload file using Google Drive API
            from googleapiclient.discovery import build
            from googleapiclient.http import MediaFileUpload
            
            service = build('drive', 'v3', credentials=credentials)
            
            file_metadata = {'name': filename}
            file_size = os.path.getsize(file_path)
            uploaded_size = 0
            last_update_time = time.time()
            last_uploaded_size = 0
            
            media = MediaFileUpload(
                file_path,
                resumable=True,
                chunksize=1024*1024,
                mimetype='video/mp4'
            )
            
            request = service.files().create(
                body=file_metadata,
                media_body=media,
                fields='id',
                supportsAllDrives=True
            )
            
            response = None
            while response is None:
                status, response = request.next_chunk()
                if status:
                    uploaded_size = status.resumable_progress
                    current_time = time.time()
                    
                    if current_time - last_update_time >= 3:
                        progress = (uploaded_size / file_size) * 100
                        bar_length = 20
                        filled_length = int(progress * bar_length / 100)
                        bar = '█' * filled_length + '░' * (bar_length - filled_length)
                        
                        # Calculate speed based on difference since last update
                        speed = (uploaded_size - last_uploaded_size) / (current_time - last_update_time)
                        eta = (file_size - uploaded_size) / speed if speed > 0 else 0
                        
                        progress_text = (
                            f"⬆️ Drive এ আপলোড হচ্ছে...\n\n"
                            f"👤 ইউজার: {username}\n"
                            f"📁 ফাইল: {filename}\n"
                            f"┌ প্রোগ্রেস: {progress:.1f}%\n"
                            f"├ {bar}\n"
                            f"├ সাইজ: {self.format_size(uploaded_size)} / {self.format_size(file_size)}\n"
                            f"├ স্পীড: {self.format_size(speed)}/s\n"
                            f"└ বাকি সময়: {self.format_time(eta)}"
                        )
                        
                        await status_message.edit_text(progress_text)
                        
                        # Update for next iteration
                        last_update_time = current_time
                        last_uploaded_size = uploaded_size
            
            file_id = response.get('id')
            
            # Make the file publicly accessible
            service.permissions().create(
                fileId=file_id,
                body={'type': 'anyone', 'role': 'reader'},
                fields='id'
            ).execute()
            
            # Get sharing link
            file = service.files().get(
                fileId=file_id,
                fields='webViewLink'
            ).execute()
            
            return file.get('webViewLink')
            
        except Exception as e:
            raise Exception(f"Drive upload error: {str(e)}")

    def format_size(self, size):
        """Format file size"""
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size < 1024.0:
                return f"{size:.1f} {unit}"
            size /= 1024.0

    def format_time(self, seconds):
        """Format time in seconds to readable format"""
        minutes, seconds = divmod(int(seconds), 60)
        hours, minutes = divmod(minutes, 60)
        if hours > 0:
            return f"{hours}h {minutes}m {seconds}s"
        elif minutes > 0:
            return f"{minutes}m {seconds}s"
        else:
            return f"{seconds}s"