import streamlit as st
import serpapi
import pandas as pd
import os
from concurrent.futures import ThreadPoolExecutor

# Set page config for a better look
st.set_page_config(page_title="Pycon Plate Navigator", page_icon="🍜", layout="wide")

st.title("🍜 PyCon Plate Navigator")
st.markdown("### Find local spots that accommodate your dietary needs.")

# Sidebar for inputs
with st.sidebar:
    st.header("Search Parameters")
    location_name = st.selectbox("📍 Select Location", ["PyCon US 2026"])
    
    # Map selection to address
    if location_name == "PyCon US 2026":
        location = "300 E Ocean Blvd, Long Beach, CA 90802"
    else:
        location = "300 E Ocean Blvd, Long Beach, CA 90802" # Fallback
        
    cuisine = st.text_input("🍱 Cuisine (e.g., Japanese, Vietnamese)", "Vietnamese")
    avoid = st.text_input("🚫 Ingredient to avoid", "onions")
    
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
        with st.spinner(f"Searching for {cuisine} in {location}..."):
            params = {
                "engine": "google_maps",
                "q": f"{cuisine} restaurants in {location}",
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

                    # 2. Fetch reviews for this place to check for the avoided ingredient
                    review_params = {
                        "engine": "google_maps_reviews",
                        "data_id": data_id
                    }
                    mentions = []
                    try:
                        reviews_result = client.search(review_params)
                        reviews = reviews_result.get("reviews", [])
                        
                        for r in reviews:
                            snippet = r.get("snippet", "").lower()
                            if avoid.lower() in snippet:
                                mentions.append(r.get("snippet"))
                    except Exception:
                        pass
                    
                    return {
                        "Title": title,
                        "Rating": place.get("rating"),
                        "Reviews": place.get("reviews"),
                        "Address": place.get("address"),
                        "Distance": distance_text,
                        "distance_val": distance_val,
                        "Mentions": mentions,
                        "Links": place.get("links", {}).get("directions"),
                        "lat": place.get("gps_coordinates", {}).get("latitude"),
                        "lon": place.get("gps_coordinates", {}).get("longitude")
                    }

                safe_spots = []
                # Use ThreadPoolExecutor to process places in parallel
                with ThreadPoolExecutor(max_workers=5) as executor:
                    # We still want to show progress, so we can use map or as_completed
                    # However, to keep it simple and show which one is being processed, we can use a loop
                    # but it's better to just fire them all and collect results
                    futures = [executor.submit(process_place, place) for place in results]
                    for i, future in enumerate(futures):
                        title = results[i].get("title")
                        status_text.text(f"Processing {i+1}/{len(results)}: {title}...")
                        progress_bar.progress((i) / len(results))
                        safe_spots.append(future.result())

                progress_bar.empty()
                status_text.empty()

                # Sort by walking distance
                safe_spots.sort(key=lambda x: x['distance_val'])

                # Only show top 5 spots
                display_spots = safe_spots[:5]

                # Display Results
                for spot in display_spots:
                    with st.expander(f"{spot['Title']} - {spot['Distance']} walk - {spot['Rating']}⭐ ({len(spot['Mentions'])} mentions of '{avoid}')"):
                        col1, col2 = st.columns([2, 1])
                        with col1:
                            if spot['Links']:
                                st.markdown(f"**Address:** [{spot['Address']}]({spot['Links']})")
                            else:
                                st.write(f"**Address:** {spot['Address']}")
                            
                            if spot['Mentions']:
                                st.write(f"**Review snippets mentioning '{avoid}':**")
                                for m in spot['Mentions']:
                                    st.info(f"\"{m}\"")
                            else:
                                st.success(f"No recent reviews mention '{avoid}'.")
                        
                        with col2:
                            if spot['Links']:
                                st.link_button("View on Maps", spot['Links'])
                
                # Show Map
                df = pd.DataFrame(display_spots)
                if not df.empty and "lat" in df.columns and "lon" in df.columns:
                    st.divider()
                    st.subheader("Map View")
                    # Streamlit's st.map uses the 'name' or 'label' column for tooltips/labels if available
                    map_df = df.dropna(subset=['lat', 'lon']).copy()
                    map_df['label'] = map_df['Title']
                    st.map(map_df)