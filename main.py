import streamlit as st
import serpapi
import os
import re
import logging
from concurrent.futures import ThreadPoolExecutor

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Constants
DEFAULT_LOCATION = "300 E Ocean Blvd, Long Beach, CA 90802"
WALKING_MODE = 2


def get_serpapi_key():
    """Securely get API key from environment or user input."""
    api_key = os.getenv("SERP_API_KEY")
    if not api_key:
        api_key = st.sidebar.text_input(
            "🔑 SerpApi Key",
            type="password",
            help="Enter your SerpApi key. For deployment, use secrets.",
        )
    else:
        st.sidebar.info("✅ SerpApi Key loaded from environment.")
    return api_key


@st.cache_data(show_spinner=False)
def search_restaurants(api_key, query, location):
    """Search for restaurants using SerpApi."""
    client = serpapi.Client(api_key=api_key)
    params = {
        "engine": "google_maps",
        "q": f"{query} in {location}",
        "type": "search",
    }
    # Only use hardcoded LL if it's the default location to avoid bias for other addresses
    if location == DEFAULT_LOCATION:
        params["ll"] = "@33.7658273,-118.1899613,15z"

    return client.search(params).get("local_results", [])


@st.cache_data(show_spinner=False)
def get_walking_distance(api_key, start_location, end_address, title):
    """Fetch walking distance between two locations."""
    client = serpapi.Client(api_key=api_key)
    dir_params = {
        "engine": "google_maps_directions",
        "start_addr": start_location,
        "end_addr": end_address,
        "travel_mode": WALKING_MODE,
    }
    try:
        results = client.search(dir_params)
        if results.get("error"):
            logger.error(
                f"Error fetching directions for {title}: {results.get('error')}"
            )
            return "Unknown", 999999

        directions = results.get("directions", [])
        if directions:
            best_route = directions[0]
            return best_route.get("formatted_distance", "Unknown"), best_route.get(
                "distance", 999999
            )
    except Exception:
        logger.exception(f"Unexpected error fetching directions for {title}")
    return "Unknown", 999999


@st.cache_data(show_spinner=False)
def get_review_mentions(api_key, data_id, avoid_list, title):
    """Fetch reviews and check for items to avoid."""
    client = serpapi.Client(api_key=api_key)
    mentions = {}
    try:
        results = client.search({"engine": "google_maps_reviews", "data_id": data_id})
        for review in results.get("reviews", []):
            snippet = review.get("snippet", "").lower()
            for item in avoid_list:
                if item in snippet:
                    mentions.setdefault(item, []).append(review.get("snippet"))
    except Exception:
        logger.exception(f"Unexpected error fetching reviews for {title}")
    return mentions


def process_place(api_key, place, start_location, avoid_list):
    """Process a single place: fetch distance and reviews."""
    title = place.get("title")
    address = place.get("address")

    distance_text, distance_val = get_walking_distance(
        api_key, start_location, address, title
    )
    mentions = get_review_mentions(api_key, place.get("data_id"), avoid_list, title)

    link = place.get("links", {}).get("directions")
    if not link:
        query = f"{title} {address or ''}".strip()
        link = (
            f"https://www.google.com/maps/search/?api=1&query={query.replace(' ', '+')}"
        )

    return {
        "Title": title,
        "Rating": place.get("rating"),
        "Reviews": place.get("reviews"),
        "Address": address,
        "Distance": distance_text,
        "distance_val": distance_val,
        "Mentions": mentions,
        "Links": link,
    }


def display_spot(spot, avoids, wants):
    """Render a single spot in Streamlit."""
    mention_count = sum(len(m) for m in spot["Mentions"].values())
    avoid_label = avoids if avoids else "anything"

    with st.expander(
        f"{spot['Title']} - {spot['Distance']} walk - {spot['Rating']}⭐ ({mention_count} mentions of items to avoid)"
    ):
        st.markdown(f"**Address:** [{spot['Address']}]({spot['Links']})")

        if spot["Mentions"]:
            avoid_list = [a.strip() for a in avoids.split(",") if a.strip()]
            want_list = [w.strip() for w in wants.split(",") if w.strip()]
            for item, snippets in spot["Mentions"].items():
                st.write(f"**Review snippets mentioning '{item}':**")
                for snippet in snippets:
                    highlighted = snippet
                    for avoid_item in avoid_list:
                        pattern = re.compile(re.escape(avoid_item), re.IGNORECASE)
                        highlighted = pattern.sub(
                            r'<span style="color:red; font-weight:bold;">\g<0></span>',
                            highlighted,
                        )
                    for want_item in want_list:
                        pattern = re.compile(re.escape(want_item), re.IGNORECASE)
                        highlighted = pattern.sub(
                            r'<span style="color:green; font-weight:bold;">\g<0></span>',
                            highlighted,
                        )
                    st.markdown(
                        f"<blockquote>{highlighted}</blockquote>",
                        unsafe_allow_html=True,
                    )
        else:
            st.success(f"No recent reviews mention items to avoid ({avoid_label}).")


def main():
    st.set_page_config(
        page_title="Pycon Plate Navigator", page_icon="🍜", layout="wide"
    )
    st.title("🍜 PyCon Plate Navigator")
    st.markdown("### Find local spots that accommodate everyone's dietary needs.")

    # Sidebar
    with st.sidebar:
        st.header("Search Parameters")
        location_input = st.text_input(
            "📍 Location",
            "PyCon US 2026",
            help="Type 'PyCon US 2026' or any custom address.",
        )
        location = (
            DEFAULT_LOCATION
            if location_input.strip().lower() == "pycon us 2026"
            else location_input
        )

        wants = st.text_input(
            "🍱 What people want (e.g., Japanese, Vietnamese)", "Vietnamese"
        )
        avoids = st.text_input("🚫 What to avoid", "onions")
        api_key = get_serpapi_key()

    if st.button("Find Spots Nearby"):
        if not api_key:
            st.error("Please provide a SerpApi key.")
            return

        search_query = wants if wants else "restaurants"
        with st.spinner(f"Searching for {search_query} in {location}..."):
            results = search_restaurants(api_key, search_query, location)
            results = [r for r in results if r.get("rating") and r.get("rating") >= 4.0]

            if not results:
                st.warning("No results found with 4+ stars. Try a different search.")
                return

            results_header = st.empty()
            results_header.subheader(
                "Analyzing results and finding top 5 closest spots..."
            )
            progress_bar = st.progress(0)
            status_text = st.empty()

            avoid_list = tuple(
                a.strip().lower() for a in avoids.split(",") if a.strip()
            )
            safe_spots = []

            with ThreadPoolExecutor(max_workers=10) as executor:
                futures = [
                    executor.submit(process_place, api_key, p, location, avoid_list)
                    for p in results[:10]
                ]
                for i, future in enumerate(futures):
                    status_text.text(
                        f"Processing {i + 1}/{len(futures)}: {results[i].get('title')}..."
                    )
                    progress_bar.progress(i / len(futures))
                    safe_spots.append(future.result())

            progress_bar.empty()
            status_text.empty()
            results_header.subheader("Top 5 closest spots:")

            safe_spots.sort(key=lambda x: x["distance_val"])
            for spot in safe_spots[:5]:
                display_spot(spot, avoids, wants)


if __name__ == "__main__":
    main()
