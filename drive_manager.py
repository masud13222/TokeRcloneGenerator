import os
import pickle
import json
import configparser
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from urllib.parse import urlparse, parse_qs

class DriveManager:
    def __init__(self):
        self.service = None
        
    def _extract_file_id(self, url: str) -> str:
        """Extract file ID from Google Drive URL"""
        try:
            if "folders" in url:
                # Folder URL
                return url.split("/")[-1]
            elif "file/d/" in url:
                # File URL
                return url.split("/")[5]
            elif "id=" in url:
                # Shared drive URL
                parsed = urlparse(url)
                return parse_qs(parsed.query)['id'][0]
            else:
                return url
        except:
            return url
            
    def _get_credentials(self, rclone_conf=None, token_pickle=None):
        """Get credentials from either rclone.conf or token.pickle"""
        try:
            if rclone_conf:
                # Read rclone.conf
                config = configparser.ConfigParser()
                config.read(rclone_conf)
                
                if 'gdrive' not in config:
                    raise Exception("Invalid rclone.conf file")
                    
                # Get token data
                token_data = json.loads(config['gdrive']['token'])
                
                return Credentials(
                    token=token_data.get('access_token'),
                    refresh_token=token_data.get('refresh_token'),
                    token_uri="https://oauth2.googleapis.com/token",
                    client_id=token_data.get('client_id'),
                    client_secret=token_data.get('client_secret'),
                    scopes=['https://www.googleapis.com/auth/drive']
                )
                
            elif token_pickle:
                # Read token.pickle
                with open(token_pickle, 'rb') as token:
                    return pickle.load(token)
                    
            return None
            
        except Exception as e:
            print(f"Failed to get credentials: {str(e)}")
            return None
            
    async def clone_file(self, url: str, rclone_conf=None, token_pickle=None):
        """Clone file/folder to drive root"""
        try:
            # Get credentials
            creds = self._get_credentials(rclone_conf, token_pickle)
            if not creds:
                raise Exception("Failed to get valid credentials")
                
            # Build service
            self.service = build('drive', 'v3', credentials=creds)
            
            # Get file ID
            file_id = self._extract_file_id(url)
            
            # Get file metadata
            file = self.service.files().get(
                fileId=file_id,
                supportsAllDrives=True,
                fields='id, name, mimeType'
            ).execute()
            
            if file['mimeType'] == 'application/vnd.google-apps.folder':
                # Clone folder
                return await self._clone_folder(file_id)
            else:
                # Clone file
                return await self._clone_file(file_id)
                
        except Exception as e:
            print(f"Clone error: {str(e)}")
            return None
            
    async def _clone_file(self, file_id: str):
        """Clone single file"""
        try:
            # Copy file
            copied_file = self.service.files().copy(
                fileId=file_id,
                supportsAllDrives=True,
                fields='id, name, webViewLink'
            ).execute()
            
            return {
                'id': copied_file['id'],
                'name': copied_file['name'],
                'link': copied_file['webViewLink']
            }
            
        except Exception as e:
            print(f"File clone error: {str(e)}")
            return None
            
    async def _clone_folder(self, folder_id: str):
        """Clone folder and its contents"""
        try:
            # Get source folder details
            folder = self.service.files().get(
                fileId=folder_id,
                supportsAllDrives=True,
                fields='name'
            ).execute()
            
            # Create new folder
            new_folder = self.service.files().create(
                body={
                    'name': folder['name'],
                    'mimeType': 'application/vnd.google-apps.folder'
                },
                fields='id, name, webViewLink'
            ).execute()
            
            # List all files in source folder
            results = []
            page_token = None
            while True:
                response = self.service.files().list(
                    q=f"'{folder_id}' in parents",
                    spaces='drive',
                    fields='nextPageToken, files(id, name, mimeType)',
                    supportsAllDrives=True,
                    includeItemsFromAllDrives=True,
                    pageToken=page_token
                ).execute()
                
                for file in response.get('files', []):
                    if file['mimeType'] == 'application/vnd.google-apps.folder':
                        # Recursively clone subfolder
                        sub_folder = await self._clone_folder(file['id'])
                        if sub_folder:
                            # Move subfolder to new parent
                            self.service.files().update(
                                fileId=sub_folder['id'],
                                addParents=new_folder['id'],
                                removeParents='root',
                                fields='id, parents'
                            ).execute()
                    else:
                        # Clone file
                        copied_file = await self._clone_file(file['id'])
                        if copied_file:
                            # Move file to new parent
                            self.service.files().update(
                                fileId=copied_file['id'],
                                addParents=new_folder['id'],
                                removeParents='root',
                                fields='id, parents'
                            ).execute()
                
                page_token = response.get('nextPageToken')
                if not page_token:
                    break
                    
            return {
                'id': new_folder['id'],
                'name': new_folder['name'],
                'link': new_folder['webViewLink']
            }
            
        except Exception as e:
            print(f"Folder clone error: {str(e)}")
            return None 