import spotipy
from spotipy.oauth2 import SpotifyOAuth
import streamlit as st
import os
import re
from groq import Groq

SPOTIFY_CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID")
SPOTIFY_CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET")
SPOTIFY_REDIRECT_URI = "http://localhost:8501"
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

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

def fetch_songs_and_playlist_name(mood, language, song_type, artist=None, num_songs=10):
    client = Groq(api_key=GROQ_API_KEY)

    # Refined prompt for generating songs and suggesting playlist name
    prompt = (
        f"Generate a playlist of {num_songs} {language} {song_type} songs for someone who feels {mood}. "
        f"Also suggest a creative playlist name for this mood in {language}. "
        "Each song should have a clear format as 'Track Name - Artist'."
    )

    if artist:
        prompt += f" Include popular songs from or featuring the artist {artist}."

    chat_completion = client.chat.completions.create(
        messages=[{"role": "user", "content": prompt}],
        model="llama3-8b-8192"
    )

    response = chat_completion.choices[0].message.content
    return parse_songs_and_playlist_name(response)

def parse_songs_and_playlist_name(response):
    lines = response.split("\n")

    song_pattern = re.compile(r'^\d+\.\s*"?(.+?)"?\s*-\s*(.+)$')
    
    song_list = []
    playlist_name = "My Mood Playlist"  # Default name
    playlist_name_found = False

    for line in lines:
        line = line.strip()

        if not line or " - " not in line:
            if "playlist name" in line.lower() and not playlist_name_found:
                # Look for playlist name suggestion from the model
                playlist_name = line.split(":")[-1].strip().capitalize()
                playlist_name_found = True
            continue

        match = song_pattern.match(line)
        if match:
            track_name = match.group(1).strip()
            artist_name = match.group(2).strip()

            track_name = re.sub(r"\(.*?\)", "", track_name).strip()
            artist_name = re.sub(r"\(.*?\)", "", artist_name).strip()

            song_list.append(f"{track_name} - {artist_name}")
        else:
            st.warning(f"Could not parse song data: {line}")

    unique_song_list = list(dict.fromkeys(song_list))
    return unique_song_list, playlist_name

def create_spotify_playlist(sp, song_list, playlist_name):
    if song_list:
        if not playlist_name:
            st.error("Playlist name is missing. Please enter a valid name.")
            return None

        user_id = sp.current_user()["id"]
        playlist = sp.user_playlist_create(user_id, playlist_name)

        track_ids = []
        for song in song_list:
            try:
                track_name, artist_name = song.split(" - ")

                result = sp.search(q=f"track:{track_name} artist:{artist_name}", type="track", limit=5)

                if not result['tracks']['items']:
                    result = sp.search(q=f"track:{track_name}", type="track", limit=5)

                if result['tracks']['items']:
                    st.write(f"Search results for '{track_name}':")
                    for item in result['tracks']['items']:
                        st.write(f"Track: {item['name']} by {', '.join([artist['name'] for artist in item['artists']])}")
                    
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

# Main app function with enhanced UI
def main():
    st.title("🎵 My Music Maker")
    st.subheader("Create a playlist based on your mood!")

    with st.form(key="playlist_form"):
        # User inputs
        mood = st.selectbox("Select your mood", ["Happy", "Sad", "Relaxed", "Calm", "Excited", "Silly"])
        language = st.selectbox("Select language", ["English", "Hindi", "Punjabi"])
        song_type = st.radio("Old, New, or Mix songs", ["Old", "New", "Mix"], horizontal=True)
        num_songs = st.slider("How many songs would you like in your playlist?", 5, 30, 10)
        artist_name = st.text_input("Optional: Enter artist name to include in playlist")  # Optional artist name

        submit_button = st.form_submit_button(label="Generate Playlist 🎶")

    if submit_button:
        sp = get_spotify_client()

        if sp is None:
            st.warning("Please authorize the app to use Spotify")
            return  

        song_list, suggested_playlist_name = fetch_songs_and_playlist_name(mood, language, song_type, artist_name, num_songs)

        playlist_name = st.text_input("Playlist Name", suggested_playlist_name)

        if not playlist_name:
            st.error("Please enter a valid playlist name.")
            return

        if song_list:
            st.subheader("Generated Songs 🎧")
            for song in song_list:
                st.write(song)

            save_playlist = st.radio("Do you want to save this playlist?", ("Yes", "No"), key="save_playlist_radio", horizontal=True)

            if save_playlist == "Yes":
                playlist_url = create_spotify_playlist(sp, song_list, playlist_name)

                if playlist_url:
                    st.success(f"Playlist '{playlist_name}' created successfully! 🎉")
                    st.write(f"Check out your playlist: [Spotify Playlist]({playlist_url})")
                else:
                    st.error("Failed to create the playlist. No valid songs returned.")
            else:
                st.write("Playlist was not saved.")

            regenerate = st.radio("Do you want to generate a new playlist?", ("Yes", "No"), key="regenerate_radio", horizontal=True)
            if regenerate == "Yes":
                # Use JavaScript to reload the page
                st.write('<script>location.reload()</script>', unsafe_allow_html=True)
        else:
            st.error("No songs fetched.")

if __name__ == "__main__":
    main()
