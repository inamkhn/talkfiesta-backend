"""
Google OAuth Service
Handles Google OAuth authentication flow
"""

from typing import Optional, Dict, Any
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests
from fastapi import HTTPException, status
import httpx

from app.config import settings

class GoogleOAuthService:
    """Service for Google OAuth authentication"""
    
    def __init__(self):
        self.client_id = settings.GOOGLE_CLIENT_ID
        self.client_secret = settings.GOOGLE_CLIENT_SECRET
        self.redirect_uri = settings.GOOGLE_REDIRECT_URI
        
    def get_authorization_url(self, state: Optional[str] = None) -> str:
        """
        Generate Google OAuth authorization URL
        
        Args:
            state: Optional state parameter for CSRF protection
            
        Returns:
            Authorization URL to redirect user to
        """
        base_url = "https://accounts.google.com/o/oauth2/v2/auth"
        
        params = {
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "response_type": "code",
            "scope": "openid email profile",
            "access_type": "offline",
            "prompt": "consent"
        }
        
        if state:
            params["state"] = state
        
        # Build query string
        query_string = "&".join([f"{k}={v}" for k, v in params.items()])
        return f"{base_url}?{query_string}"
    
    async def exchange_code_for_tokens(self, code: str) -> Dict[str, Any]:
        """
        Exchange authorization code for access token and ID token
        
        Args:
            code: Authorization code from Google
            
        Returns:
            Dictionary containing access_token, id_token, etc.
        """
        token_url = "https://oauth2.googleapis.com/token"
        
        data = {
            "code": code,
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "redirect_uri": self.redirect_uri,
            "grant_type": "authorization_code"
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.post(token_url, data=data)
            
            if response.status_code != 200:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Failed to exchange code for tokens"
                )
            
            return response.json()
    
    def verify_id_token(self, id_token_str: str) -> Dict[str, Any]:
        """
        Verify Google ID token and extract user info
        
        Args:
            id_token_str: ID token from Google
            
        Returns:
            Dictionary containing user info (sub, email, name, picture)
        """
        try:
            # Verify the token
            idinfo = id_token.verify_oauth2_token(
                id_token_str,
                google_requests.Request(),
                self.client_id
            )
            
            # Verify issuer
            if idinfo['iss'] not in ['accounts.google.com', 'https://accounts.google.com']:
                raise ValueError('Wrong issuer.')
            
            return idinfo
            
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Invalid ID token: {str(e)}"
            )
    
    async def get_user_info(self, access_token: str) -> Dict[str, Any]:
        """
        Get user info from Google using access token
        
        Args:
            access_token: Access token from Google
            
        Returns:
            Dictionary containing user info
        """
        userinfo_url = "https://www.googleapis.com/oauth2/v2/userinfo"
        
        headers = {
            "Authorization": f"Bearer {access_token}"
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.get(userinfo_url, headers=headers)
            
            if response.status_code != 200:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Failed to get user info from Google"
                )
            
            return response.json()
    
    async def authenticate_with_code(self, code: str) -> Dict[str, Any]:
        """
        Complete OAuth flow: exchange code and verify user
        
        Args:
            code: Authorization code from Google
            
        Returns:
            Dictionary containing user info
        """
        # Exchange code for tokens
        tokens = await self.exchange_code_for_tokens(code)
        
        # Verify ID token and get user info
        user_info = self.verify_id_token(tokens["id_token"])
        
        return {
            "google_id": user_info["sub"],
            "email": user_info["email"],
            "name": user_info.get("name", ""),
            "avatar_url": user_info.get("picture", None),
            "email_verified": user_info.get("email_verified", False)
        }
    
    async def authenticate_with_token(self, id_token_str: str) -> Dict[str, Any]:
        """
        Authenticate user with Google ID token (for frontend OAuth)
        
        Args:
            id_token_str: ID token from Google (from frontend)
            
        Returns:
            Dictionary containing user info
        """
        # Verify ID token and get user info
        user_info = self.verify_id_token(id_token_str)
        
        return {
            "google_id": user_info["sub"],
            "email": user_info["email"],
            "name": user_info.get("name", ""),
            "avatar_url": user_info.get("picture", None),
            "email_verified": user_info.get("email_verified", False)
        }
