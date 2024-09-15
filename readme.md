# Python Script for Retrieving Data from the Spotify API

This Python script retrieves track information from the Spotify API based on a list of artists and song titles provided in a CSV file.

## Key Functionality

- **Authentication**: The script starts by authenticating with the Spotify API using client credentials.
- **Data Loading**: It reads artist and track information from a CSV file named `artist.csv`.
- **Spotify API Calls**: The script constructs a search query for each artist-track pair and sends a request to the Spotify API.
- **Data Extraction**: Upon successful API response, the script extracts relevant track details such as ID, name, artist, album, popularity, and release year.
- **Duplicate Handling**: It checks for duplicate tracks and avoids adding them to the results.
- **Data Storage**: The retrieved track information is written to another CSV file named `results.csv`.
- **Progress Tracking**: The script displays the processing progress and estimates the remaining time.
- **Error Handling**: It includes basic error handling to manage situations like API request failures or rate limiting.
