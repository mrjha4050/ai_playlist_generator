import streamlit as st
import os
import webbrowser
import requests
import base64
import urllib.parse as urlparse
from urllib.parse import parse_qs
import json

# Spotify API Credentials
SPOTIFY_CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID")
SPOTIFY_CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET")
SPOTIFY_REDIRECT_URI = "http://localhost:8501"  

# Spotify OAuth URLs
AUTH_URL = 'https://accounts.spotify.com/authorize'
TOKEN_URL = 'https://accounts.spotify.com/api/token'
SCOPE = "playlist-modify-public"

# Global variable to store tokens
access_token = None
refresh_token = None

def authorize_spotify():
    auth_url = AUTH_URL + "?" + urllib.parse.urlencode({
        'response_type': 'code',
        'client_id': SPOTIFY_CLIENT_ID,
        'scope': SCOPE,
        'redirect_uri': SPOTIFY_REDIRECT_URI,
    })
    st.write(f"[Click here to authorize Spotify]({auth_url})")
    webbrowser.open(auth_url)
    st.stop()

# Step 2: Handle the redirect and extract authorization code
def handle_redirect():
    query_params = st.experimental_get_query_params()
    if 'code' in query_params:
        code = query_params['code'][0]
        return code
    return None

# Step 3: Exchange the authorization code for an access token
def get_access_token(auth_code):
    auth_str = f"{SPOTIFY_CLIENT_ID}:{SPOTIFY_CLIENT_SECRET}"
    b64_auth_str = base64.urlsafe_b64encode(auth_str.encode()).decode()

    headers = {
        "Authorization": f"Basic {b64_auth_str}",
        "Content-Type": "application/x-www-form-urlencoded"
    }

    data = {
        "grant_type": "authorization_code",
        "code": auth_code,
        "redirect_uri": SPOTIFY_REDIRECT_URI
    }

    response = requests.post(TOKEN_URL, headers=headers, data=data)
    
    if response.status_code == 200:
        token_data = response.json()
        global access_token, refresh_token
        access_token = token_data['access_token']
        refresh_token = token_data['refresh_token']
        st.success("Successfully authenticated with Spotify!")
        return access_token
    else:
        st.error("Failed to fetch access token.")
        return None

# Function to refresh access token using refresh_token
def refresh_access_token():
    auth_str = f"{SPOTIFY_CLIENT_ID}:{SPOTIFY_CLIENT_SECRET}"
    b64_auth_str = base64.urlsafe_b64encode(auth_str.encode()).decode()

    headers = {
        "Authorization": f"Basic {b64_auth_str}",
        "Content-Type": "application/x-www-form-urlencoded"
    }

    data = {
        "grant_type": "refresh_token",
        "refresh_token": refresh_token
    }

    response = requests.post(TOKEN_URL, headers=headers, data=data)

    if response.status_code == 200:
        token_data = response.json()
        global access_token
        access_token = token_data['access_token']
        st.success("Token refreshed successfully!")
    else:
        st.error("Failed to refresh access token.")

# Example function to use the access token to interact with Spotify API
def fetch_user_profile():
    headers = {
        "Authorization": f"Bearer {access_token}"
    }

    response = requests.get("https://api.spotify.com/v1/me", headers=headers)

    if response.status_code == 200:
        user_data = response.json()
        st.write(f"Logged in as: {user_data['display_name']}")
    else:
        st.error("Failed to fetch user profile.")

# Main application flow
def main():
    st.title("Spotify OAuth Example")

    # Check if access_token is available
    if access_token:
        fetch_user_profile()
        if st.button("Refresh Token"):
            refresh_access_token()
    else:
        # Start OAuth process by redirecting the user to Spotify login
        if st.button("Authorize Spotify"):
            authorize_spotify()

        # Handle redirect and get authorization code
        auth_code = handle_redirect()
        if auth_code:
            get_access_token(auth_code)

if __name__ == "__main__":
    main()
