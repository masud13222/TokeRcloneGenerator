import pickle
import os
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request

class TokenManager:
    def __init__(self):
        self.token_file = "token.pickle"
        self.scopes = ["https://www.googleapis.com/auth/drive"]
        self.credentials_content = None  # Store credentials content
        
    def get_auth_url(self, credentials_file: str):
        """Get authorization URL"""
        # Read and store credentials content
        with open(credentials_file, 'r') as f:
            self.credentials_content = f.read()
            
        flow = InstalledAppFlow.from_client_secrets_file(
            credentials_file,
            self.scopes
        )
        
        # Set redirect URI
        flow.redirect_uri = "http://127.0.0.1:53682"
        
        auth_url = flow.authorization_url()[0]
        return auth_url
        
    async def generate_token(self, code: str) -> bool:
        """Generate token from auth code"""
        try:
            if not self.credentials_content:
                return False
                
            # Write credentials content to temp file
            with open("temp_cred.json", 'w') as f:
                f.write(self.credentials_content)
                
            flow = InstalledAppFlow.from_client_secrets_file(
                "temp_cred.json",
                self.scopes
            )
            
            # Set redirect URI
            flow.redirect_uri = "http://127.0.0.1:53682"
            
            # Get credentials
            flow.fetch_token(code=code)
            credentials = flow.credentials
            
            # Save the credentials
            with open(self.token_file, 'wb') as token:
                pickle.dump(credentials, token)
                
            # Cleanup
            os.remove("temp_cred.json")
            
            return True
            
        except Exception as e:
            print(f"Token generation error: {str(e)}")
            if os.path.exists("temp_cred.json"):
                os.remove("temp_cred.json")
            return False 