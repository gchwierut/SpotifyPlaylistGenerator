import requests
import json
from base64 import b64encode
import time
import csv
import os
import pandas as pd

# Hardcoded Spotify credentials
SPOTIFY_CLIENT_ID = 'yourclientid'
SPOTIFY_CLIENT_SECRET = 'yourclientsecret'

def update_processed_status(filename, track_title):
    """Updates the PROCESSED status in artist.csv for a given track."""
    df = pd.read_csv(filename, low_memory=False)  # Set low_memory=False
    df.loc[df['Title'] == track_title, 'PROCESSED'] = 'Yes'
    df.to_csv(filename, index=False)

def remove_duplicate_tracks(filename, track_id):
    """Checks if a track ID already exists in the results CSV."""
    if os.path.exists(filename):
        with open(filename, "r", encoding="utf-8") as csvfile:
            reader = csv.reader(csvfile)
            for row in reader:
                if row and row[1] == track_id:
                    return True
    return False

def get_retrieved_tracks_count(filename):
    """Counts the number of tracks already retrieved from results.csv."""
    if os.path.exists(filename):
        with open(filename, "r", encoding="utf-8") as csvfile:
            reader = csv.reader(csvfile)
            return sum(1 for row in reader if row and row[1].startswith("https://open.spotify.com/track/"))
    return 0

# Ensure results.csv exists with the correct headers
if not os.path.exists("results.csv"):
    with open("results.csv", "w", newline="", encoding="utf-8") as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(["Year", "Track ID", "Track Name", "Artist ID", "Artist Name", "Album ID", "Popularity"])

# Hardcoded Spotify credentials
auth_headers = {"Authorization": f"Basic {b64encode(f'{SPOTIFY_CLIENT_ID}:{SPOTIFY_CLIENT_SECRET}'.encode()).decode()}"}
auth_data = {"grant_type": "client_credentials"}
auth_response = requests.post("https://accounts.spotify.com/api/token", headers=auth_headers, data=auth_data)
if auth_response.status_code != 200:
    print("Authentication failed.")
    exit()
access_token = json.loads(auth_response.text)["access_token"]
headers = {"Authorization": f"Bearer {access_token}"}

# Check if artist.csv exists and add a PROCESSED column if missing
if os.path.exists("artist.csv"):
    with open("artist.csv", "r+", encoding="utf-8") as csvfile:
        reader = csv.DictReader(csvfile)
        fieldnames = reader.fieldnames
        if "PROCESSED" not in fieldnames:
            fieldnames.append("PROCESSED")
            all_rows = list(reader)
            csvfile.seek(0)
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            for row in all_rows:
                row["PROCESSED"] = "No"
                writer.writerow(row)

tracks_to_search = []
with open("artist.csv", "r", encoding="utf-8") as csvfile:
    reader = csv.DictReader(csvfile)
    for row in reader:
        if row.get("PROCESSED", "No") == "No":
            year = row.get("Year", "")  # Get year from artist.csv
            year = int(year) if year.isdigit() else year  # Ensure year is an integer, if it's not empty
            tracks_to_search.append((row["Artist"], row["Title"], year))

total_tracks = len(tracks_to_search)

# Total goal of tracks to retrieve
goal_tracks = 10000

# Calculate the number of tracks already processed from results.csv
processed_count = get_retrieved_tracks_count("results.csv")

# Calculate the remaining tracks to retrieve
remaining_tracks = goal_tracks - processed_count

# Ask the user for the maximum number of tracks to retrieve
try:
    max_tracks = int(input(f"Enter the maximum number of tracks to retrieve (up to {remaining_tracks} remaining): "))
    max_tracks = min(max_tracks, remaining_tracks)  # Ensure max_tracks does not exceed remaining tracks
except ValueError:
    print(f"Invalid number. Defaulting to retrieving {remaining_tracks} tracks.")
    max_tracks = remaining_tracks

# Limit the number of tracks to the maximum specified by the user
tracks_to_search = tracks_to_search[:max_tracks]

# Start processing from the first unprocessed track
processed_tracks = 0

endpoint = "https://api.spotify.com/v1/search"

existing_track_ids = set()

start_time = time.time()
track_times = []

# Track API calls
api_call_count = 0
call_start_time = time.time()

# Process each track
for artist, title, year in tracks_to_search:
    start_track_time = time.time()  # Track the start time of the current track processing
    processed_tracks += 1

    # Update total processed count including previously processed tracks
    total_processed = processed_count + processed_tracks

    # Print the progress, reflecting the total goal of 10,000 tracks
    print(f"Processing track {total_processed}/{goal_tracks} ({total_processed/goal_tracks*100:.2f}%)")
    print(f"Current Track: Artist - {artist}, Title - {title}")

    query = f"artist:\"{artist}\" track:{title}"
    search_params = {"q": query, "type": "track", "limit": 1, "market": "PL"}

    # Wait if API call limit is reached
    if api_call_count >= 180:
        elapsed_time = time.time() - call_start_time
        if elapsed_time < 60:
            wait_time = 60 - elapsed_time
            print(f"API call limit reached. Waiting for {wait_time:.2f} seconds.")
            time.sleep(wait_time)
        # Reset call count and timer
        api_call_count = 0
        call_start_time = time.time()

    try:
        response = requests.get(endpoint, headers=headers, params=search_params)
        api_call_count += 1  # Increment API call count

        if response.status_code == 429:
            retry_after = int(response.headers.get("Retry-After", 1))  # Default to 1 second if header is missing
            print(f"Rate limit exceeded. Waiting for {retry_after} seconds.")
            time.sleep(retry_after)
            continue  # Retry the current track after the wait

        if response.status_code != 200:
            print(f"Request failed for artist {artist}, track {title}. Status code: {response.status_code}")
            continue

        data = json.loads(response.text)
        tracks = data.get("tracks", {}).get("items", [])
        if not tracks:
            print(f"No results found for artist {artist}, track {title}. Searching for any song by artist.")
            query = f"artist:\"{artist}\""  # New query for any song by artist
            search_params["q"] = query
            response = requests.get(endpoint, headers=headers, params=search_params)
            data = json.loads(response.text)
            tracks = data.get("tracks", {}).get("items", [])
            if not tracks:
                print(f"No results found for artist {artist}.")
                update_processed_status("artist.csv", title)  # Mark as processed
                continue  # Move to the next track

        track_data = tracks[0]
        track_id = track_data["id"]
        track_name = track_data["name"]
        artist_id = track_data["artists"][0]["id"]
        artist_name = track_data["artists"][0]["name"]
        album_id = track_data["album"]["id"]
        popularity = track_data["popularity"]
        if not year:  # If year is not provided in artist.csv, fetch from Spotify
            release_year = track_data["album"]["release_date"][:4]
        else:
            release_year = year  # Otherwise, use the year from artist.csv

        # Format track_id as a URL
        track_id_url = f"https://open.spotify.com/track/{track_id}"

        if not remove_duplicate_tracks("results.csv", track_id_url):
            with open("results.csv", "a", newline="", encoding="utf-8") as csvfile:
                writer = csv.writer(csvfile)
                writer.writerow([int(release_year), track_id_url, track_name, artist_id, artist_name, album_id, popularity])
            existing_track_ids.add(track_id_url)

        update_processed_status("artist.csv", title)
    except requests.exceptions.RequestException as e:
        print(f"Request failed for artist {artist}, track {title}: {e}")

    # Record the time taken for this track
    track_time = time.time() - start_track_time
    track_times.append(track_time)

    # Estimate remaining time
    if track_times:
        avg_time_per_track = sum(track_times) / len(track_times)
        remaining_tracks = max_tracks - processed_tracks
        estimated_time_remaining = avg_time_per_track * remaining_tracks / 60  # Convert to minutes

        print(f"Estimated time remaining: {estimated_time_remaining:.2f} minutes")
