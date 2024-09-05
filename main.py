import spotipy
from spotipy.oauth2 import SpotifyOAuth
import streamlit as st
import os
import re
from groq import Groq

# Spotify API Credentials
SPOTIFY_CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID")
SPOTIFY_CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET")
SPOTIFY_REDIRECT_URI = "http://localhost:8501"
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

# Initialize SpotifyOAuth and return a Spotipy client
def get_spotify_client():
    sp_oauth = SpotifyOAuth(
        client_id=SPOTIFY_CLIENT_ID,
        client_secret=SPOTIFY_CLIENT_SECRET,
        redirect_uri=SPOTIFY_REDIRECT_URI,
        scope="playlist-modify-public",
        cache_path=".cache"
    )

    token_info = sp_oauth.get_cached_token()

    if token_info:
        if sp_oauth.is_token_expired(token_info):
            token_info = sp_oauth.refresh_access_token(token_info['refresh_token'])
        sp = spotipy.Spotify(auth=token_info['access_token'])
        return sp

    query_params = st.experimental_get_query_params()
    auth_code = query_params.get('code', None)

    if not auth_code:
        auth_url = sp_oauth.get_authorize_url()
        st.write(f"[Click here to authorize Spotify]({auth_url})")
        return None
    else:
        token_info = sp_oauth.get_access_token(auth_code[0])
        st.experimental_set_query_params()  # Clear query params after successful authorization
        sp = spotipy.Spotify(auth=token_info['access_token'])
        return sp

# Function to fetch generated songs from Llama 3 (or mock API)
def fetch_songs_from_llama3(mood, language, song_type, num_songs=10):
    client = Groq(api_key=GROQ_API_KEY)

    if song_type == "Mix":
        prompt = (
            f"Generate a mix of {num_songs} old and new {language} songs for someone who feels {mood}. "
            "List them in the following format: Track Name - Artist."
        )
    else:
        prompt = (
            f"Generate a playlist of {num_songs} {language} {song_type} songs for someone who feels {mood}. "
            "List them in the following format: Track Name - Artist."
        )

    chat_completion = client.chat.completions.create(
        messages=[{"role": "user", "content": prompt}],
        model="llama3-8b-8192"
    )

    song_recommendations = chat_completion.choices[0].message.content
    return parse_songs(song_recommendations)

# Function to parse songs from the generated response
def parse_songs(song_recommendations):
    lines = song_recommendations.split("\n")

    # Regular expression to match the "Track Name - Artist" pattern
    song_pattern = re.compile(r'^\d+\.\s*"?(.+?)"?\s*-\s*(.+)$')
    
    song_list = []
    for line in lines:
        # Ignore empty lines and non-song description lines
        line = line.strip()
        if not line or " - " not in line or "Here" in line:
            continue

        # Try to match each line with the song pattern
        match = song_pattern.match(line)
        if match:
            track_name = match.group(1).strip()
            artist_name = match.group(2).strip()

            # Handle cases where movie names are in parentheses
            track_name = re.sub(r"\(.*?\)", "", track_name).strip()
            artist_name = re.sub(r"\(.*?\)", "", artist_name).strip()

            song_list.append(f"{track_name} - {artist_name}")
        else:
            st.warning(f"Could not parse song data: {line}")

    unique_song_list = list(dict.fromkeys(song_list))
    return unique_song_list

def create_spotify_playlist(sp, song_list, playlist_name):
    if song_list:
        user_id = sp.current_user()["id"]
        playlist = sp.user_playlist_create(user_id, playlist_name)

        track_ids = []
        for song in song_list:
            try:
                track_name, artist_name = song.split(" - ")

                result = sp.search(q=f"track:{track_name}", type="track", limit=5)

                if result['tracks']['items']:
                    st.write(f"Top search results for '{track_name}':")
                    for item in result['tracks']['items']:
                        st.write(f"Track: {item['name']} by {', '.join([artist['name'] for artist in item['artists']])}")

                    track_id = result["tracks"]["items"][0]["uri"]
                    track_ids.append(track_id)
                else:
                    result = sp.search(q=f"track:{track_name} artist:{artist_name}", type="track", limit=1)
                    if result['tracks']['items']:
                        track_id = result["tracks"]["items"][0]["uri"]
                        track_ids.append(track_id)
                    else:
                        st.warning(f"No track found for {track_name} by {artist_name}")

            except (IndexError, ValueError):
                st.warning(f"Could not parse song data: {song}")

        if track_ids:
            sp.user_playlist_add_tracks(user_id, playlist["id"], track_ids)
            return playlist["external_urls"]["spotify"]
    return None

def main():
    st.title("My Music Maker")

    sp = get_spotify_client()

    if sp is None:
        st.warning("Please authorize the app to use Spotify")
        return  

    # User inputs
    mood = st.selectbox("Select your mood", ["Happy", "Sad"])
    language = st.selectbox("Select language", ["English", "Hindi"])
    song_type = st.radio("Old, New, or Mix songs", ["Old", "New", "Mix"])
    playlist_name = st.text_input("Enter a name for your playlist", "My Mood Playlist")  # Custom playlist name

    if st.button("Generate Playlist"):
        song_list = fetch_songs_from_llama3(mood, language, song_type)

        if song_list:
            st.subheader("Generated Songs:")
            for song in song_list:
                st.write(song)

            playlist_url = create_spotify_playlist(sp, song_list, playlist_name)

            if playlist_url:
                st.success("Playlist created successfully!")
                st.write(f"Check out your playlist: [Spotify Playlist]({playlist_url})")
            else:
                st.error("Failed to create the playlist. No valid songs returned.")
        else:
            st.error("No songs fetched.")

if __name__ == "__main__":
    main()