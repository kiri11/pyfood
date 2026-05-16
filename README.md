# PyCon Plate Navigator 🍜

Find local spots that accommodate everyone's dietary needs.

## What this project does

[PyCon Plate Navigator](https://pyfood-2026.streamlit.app) is a Streamlit application designed for PyCon US 2026 attendees to find nearby restaurants in Long Beach that match their food preferences while helping them avoid specific ingredients or allergens.

- **Smart Search:** Searches for restaurants based on what you want (e.g., "Vietnamese", "Sushi").
- **Dietary Analysis:** Scans recent Google Maps reviews for mentions of items you want to avoid (e.g., "onions", "dairy", "peanuts").
- **Walking Distance:** Automatically calculates the walking distance from the PyCon venue (Long Beach Convention Center).
- **Interactive Results:** Displays the top 5 closest spots with expanded details and highlighted review snippets. It's hardcoded at only 5 options to avoid decision fatigue.
- **Google Maps links:** By clicking on each address, you can open the restaraunts' pages in Google Maps to see photos and other details.

It's obviously easy to add more locations. Next year it will be PyCon 2027!

## Architecture

The application is built with a focus on responsiveness and efficiency:

- **Frontend:** [Streamlit](https://streamlit.io/) provides the interactive web interface and handles the application state.
- **Backend APIs:** Powered by [SerpApi](https://serpapi.com/) to fetch real-world data from Google Maps:
    - `google_maps` engine: Finds restaurants matching the search query.
    - `google_maps_directions` engine: Retrieves precise walking distances.
    - `google_maps_reviews` engine: Fetches recent reviews for content analysis.
- **Concurrency:** Uses Python's `ThreadPoolExecutor` to process multiple restaurant candidates in parallel. Each candidate requires separate API calls for distance and reviews; parallelization ensures the "Analyzing" phase remains fast.
- **Caching:** Implements Streamlit's `@st.cache_data` to store API results. This minimizes expensive SerpApi calls and ensures a snappy user experience during UI interactions.

## Non-obvious Decisions

- **Aggressive Caching:** Every function that communicates with SerpApi is cached. Since Streamlit reruns the script on every user interaction, caching is essential to avoid hitting API rate limits and to keep the app cost-effective.
- **Parallel processing of "Top 10":** The app initialy searches for many spots but only performs deep analysis (directions + reviews) on the first 10. This balance provides a good variety of results while keeping the total processing time under a few seconds.
- **Keyword Highlighting in Snippets:** Rather than just showing a count of "mentions," the app uses Regex to inject HTML spans into review snippets. This allows it to highlight "avoid" keywords in red and "want" keywords in green directly in the UI.
- **Flexible API Key Management:** The app looks for a `SERP_API_KEY` environment variable first. If missing, it provides a secure password input in the sidebar. This allows for easy local development while being ready for secure production deployment (e.g., on Streamlit Community Cloud).

## Setup

1.  **Clone the repository.**
2.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```
3.  **Get a SerpApi Key:** Sign up at [SerpApi](https://serpapi.com/).
4.  **Run the application:**
    ```bash
    streamlit run main.py
    ```
    Alternatively, set your API key as an environment variable:
    ```bash
    export SERP_API_KEY='your_api_key_here'
    ```
