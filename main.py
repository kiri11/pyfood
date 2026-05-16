import streamlit as st
import serpapi
import os
from concurrent.futures import ThreadPoolExecutor

# Set page config for a better look
st.set_page_config(page_title="Pycon Plate Navigator", page_icon="🍜", layout="wide")

st.title("🍜 PyCon Plate Navigator")
st.markdown("### Find local spots that accommodate everyone's dietary needs.")

# Sidebar for inputs
with st.sidebar:
    st.header("Search Parameters")
    location_name = st.selectbox("📍 Select Location", ["PyCon US 2026"])
    
    # Map selection to address
    if location_name == "PyCon US 2026":
        location = "300 E Ocean Blvd, Long Beach, CA 90802"
    else:
        location = "300 E Ocean Blvd, Long Beach, CA 90802" # Fallback
        
    wants = st.text_input("🍱 What people want (e.g., Japanese, Vietnamese)", "Vietnamese")
    avoids = st.text_input("🚫 What to avoid", "onions")
    
    # Securely get API key from environment or secrets
    api_key = os.getenv("SERP_API_KEY")
    
    if not api_key:
        api_key = st.text_input("🔑 SerpApi Key", type="password", help="Enter your SerpApi key. For deployment, use secrets.")
    else:
        st.info("✅ SerpApi Key loaded from environment.")

if st.button("Find Safe Spots"):
    if not api_key:
        st.error("Please provide a SerpApi key.")
    else:
        # Prepare search query
        search_query = wants if wants else "restaurants"
        with st.spinner(f"Searching for {search_query} in {location}..."):
            params = {
                "engine": "google_maps",
                "q": f"{search_query} in {location}",
                "api_key": api_key,
                "ll": "@33.7658273,-118.1899613,15z",
                "type": "search"
            }

            client = serpapi.Client(api_key=api_key)
            results = client.search(params).get("local_results", [])

            if not results:
                st.warning("No results found. Try a different search.")
            else:
                st.subheader("Analyzing results and finding top 5 closest spots...")
                
                progress_bar = st.progress(0)
                status_text = st.empty()
                
                def process_place(place):
                    data_id = place.get("data_id")
                    title = place.get("title")
                    
                    # 1. Fetch walking distance
                    distance_val = 999999 # Default for sorting if not found
                    distance_text = "Unknown"
                    
                    dir_params = {
                        "engine": "google_maps_directions",
                        "start_addr": location,
                        "end_addr": place.get("address"),
                        "travel_mode": 2 # 2 is Walking in Google Maps Directions API
                    }
                    try:
                        directions_result = client.search(dir_params)
                        if directions_result.get("error"):
                            # Using get here to avoid potential KeyErrors if error is present but not as a string
                            pass
                        
                        directions = directions_result.get("directions", [])
                        if directions:
                            # Usually the first direction is the best
                            best_route = directions[0]
                            distance_text = best_route.get("formatted_distance", "Unknown")
                            # Extract distance in meters for sorting
                            distance_val = best_route.get("distance", 999999)
                    except Exception:
                        pass

                    # 2. Fetch reviews for this place to check for things to avoid
                    review_params = {
                        "engine": "google_maps_reviews",
                        "data_id": data_id
                    }
                    mentions = {} # Use dict to track which avoid-item was mentioned
                    avoid_list = [a.strip().lower() for a in avoids.split(",") if a.strip()]
                    try:
                        reviews_result = client.search(review_params)
                        reviews = reviews_result.get("reviews", [])
                        
                        for r in reviews:
                            snippet = r.get("snippet", "").lower()
                            for a in avoid_list:
                                if a in snippet:
                                    if a not in mentions:
                                        mentions[a] = []
                                    mentions[a].append(r.get("snippet"))
                    except Exception:
                        pass
                    
                    # 3. Ensure a link to Google Maps is available
                    link = place.get("links", {}).get("directions")
                    if not link:
                        # Fallback: create a search link based on the title and address
                        query = f"{title} {place.get('address', '')}".strip()
                        link = f"https://www.google.com/maps/search/?api=1&query={query.replace(' ', '+')}"

                    return {
                        "Title": title,
                        "Rating": place.get("rating"),
                        "Reviews": place.get("reviews"),
                        "Address": place.get("address"),
                        "Distance": distance_text,
                        "distance_val": distance_val,
                        "Mentions": mentions,
                        "Links": link
                    }

                safe_spots = []
                # Use ThreadPoolExecutor to process places in parallel
                with ThreadPoolExecutor(max_workers=10) as executor:
                    # We still want to show progress, so we can use map or as_completed
                    # However, to keep it simple and show which one is being processed, we can use a loop
                    # but it's better to just fire them all and collect results
                    futures = [executor.submit(process_place, place) for place in results[:10]]
                    for i, future in enumerate(futures):
                        title = results[i].get("title")
                        status_text.text(f"Processing {i+1}/{len(futures)}: {title}...")
                        progress_bar.progress((i) / len(futures))
                        safe_spots.append(future.result())

                progress_bar.empty()
                status_text.empty()

                # Sort by walking distance
                safe_spots.sort(key=lambda x: x['distance_val'])

                # Only show top 5 spots
                display_spots = safe_spots[:5]

                # Display Results
                for spot in display_spots:
                    mention_count = sum(len(m) for m in spot['Mentions'].values())
                    avoid_label = avoids if avoids else "anything"
                    with st.expander(f"{spot['Title']} - {spot['Distance']} walk - {spot['Rating']}⭐ ({mention_count} mentions of items to avoid)"):
                        st.markdown(f"**Address:** [{spot['Address']}]({spot['Links']})")
                        
                        if spot['Mentions']:
                            for item, snippets in spot['Mentions'].items():
                                st.write(f"**Review snippets mentioning '{item}':**")
                                for m in snippets:
                                    st.info(f"\"{m}\"")
                        else:
                            st.success(f"No recent reviews mention items to avoid ({avoid_label}).")
                