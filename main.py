import spotipy
from spotipy.oauth2 import SpotifyOAuth
import streamlit as st
import os
from urllib.parse import urlparse
import matplotlib.pyplot as plt
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

    auth_code = st.experimental_get_query_params().get('code', None)

    if not auth_code:
        auth_url = sp_oauth.get_authorize_url()
        st.write(f"[Click here to authorize Spotify]({auth_url})")
        return None  
    else:
        token_info = sp_oauth.get_access_token(auth_code[0])
        st.experimental_set_query_params()  
        sp = spotipy.Spotify(auth=token_info['access_token'])
        return sp

def fetch_songs_from_llama3(mood, language, song_type, num_songs=10):
    client = Groq(api_key=GROQ_API_KEY)

    # Customize the prompt based on input
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
    return song_recommendations.split("\n")

def fetch_global_trending_songs(sp):
    global_top_50_playlist_id = "37i9dQZEVXbMDoHDwVN2tF"  
    results = sp.playlist_tracks(global_top_50_playlist_id)

    trending_songs = []
    for item in results["items"][:5]:
        track = item["track"]
        track_name = track["name"]
        artist_name = track["artists"][0]["name"]
        popularity = track["popularity"]
        trending_songs.append((track_name, artist_name, popularity))

    return trending_songs

# Function to create Spotify playlist with a custom name
def create_spotify_playlist(sp, song_list, playlist_name):
    if song_list:
        user_id = sp.current_user()["id"]
        playlist = sp.user_playlist_create(user_id, playlist_name)

        # Search and add songs to the playlist
        track_ids = []
        for song in song_list:
            try:
                track_name, artist_name = song.split(" - ")
                result = sp.search(q=f"track:{track_name} artist:{artist_name}", type="track", limit=1)
                track_id = result["tracks"]["items"][0]["uri"]
                track_ids.append(track_id)
            except (IndexError, ValueError):
                st.warning(f"Could not find {song} on Spotify")

        if track_ids:
            sp.user_playlist_add_tracks(user_id, playlist["id"], track_ids)
            return playlist["external_urls"]["spotify"]
    return None

def plot_top_3_trending_songs(trending_songs):
    top_3_songs = trending_songs[:3]
    track_names = [f"{song[0]} - {song[1]}" for song in top_3_songs]
    popularity_scores = [song[2] for song in top_3_songs]

    fig, ax = plt.subplots()
    ax.barh(track_names, popularity_scores, color="skyblue")
    ax.set_xlabel("Popularity Score")
    ax.set_title("Top 3 Trending Songs Globally")

    st.pyplot(fig)

def main():
    st.title("My Music Maker")

    sp = get_spotify_client()

    if sp is None:
        st.warning("Please authorize the app to use Spotify")
        return  # Wait for the user to authorize before continuing

    # User inputs
    mood = st.selectbox("Select your mood", ["Happy", "Sad"])
    language = st.selectbox("Select language", ["English", "Hindi"])
    song_type = st.radio("Old, New, or Mix songs", ["Old", "New", "Mix"])
    playlist_name = st.text_input("Enter a name for your playlist", "My Mood Playlist")  # New feature for custom playlist name

    # Generate playlist when the button is clicked
    if st.button("Generate Playlist"):
        # Fetch generated songs (mocked)
        song_list = fetch_songs_from_llama3(mood, language, song_type)

        if song_list:
            st.subheader("Generated Songs:")
            for song in song_list:
                st.write(song)

            # Create Spotify playlist with the custom playlist name
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



