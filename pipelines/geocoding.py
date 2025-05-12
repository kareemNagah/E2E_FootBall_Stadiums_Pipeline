import os
import time
import requests
import json
from functools import lru_cache
from dotenv import load_dotenv

load_dotenv()


# Geocoding configuration
MAX_RETRIES = 3
RETRY_DELAY = 2  # seconds



@lru_cache(maxsize=128)
def get_location_from_nominatim(query):
    """Get location from Nominatim (OpenStreetMap) as fallback"""
    url = "https://nominatim.openstreetmap.org/search"
    params = {
        "q": query,
        "format": "json",
        "limit": 1
    }
    
    headers = {
        "User-Agent": "FootballDataEngineering/1.0"
    }
    
    for attempt in range(MAX_RETRIES):
        try:
            response = requests.get(url, params=params, headers=headers)
            
            # Handle rate limiting with retries
            if response.status_code in [429, 500, 503]:
                if attempt < MAX_RETRIES - 1:
                    print(f"⚠️ Nominatim error {response.status_code}, retrying in {RETRY_DELAY}s...")
                    time.sleep(RETRY_DELAY * (attempt + 1))
                    continue
            
            if response.status_code == 200:
                data = response.json()
                if data and len(data) > 0:
                    return (float(data[0]["lat"]), float(data[0]["lon"]))
                else:
                    print(f"⚠️ No results from Nominatim for: {query}")
                    return None
            else:
                print(f"❌ Nominatim error {response.status_code}: {response.text}")
                return None
                
        except requests.RequestException as e:
            print(f"❌ Nominatim request failed: {e}")
            if attempt < MAX_RETRIES - 1:
                time.sleep(RETRY_DELAY * (attempt + 1))
            else:
                return None
    
    return None

def get_stadium_location(country, stadium_name, city=None):
    """Get stadium location using Nominatim geocoding service"""
    # Try different query formats for better results
    # Handle different stadium name formats and locations
    queries = [
        f"{stadium_name}, {country}",  # Basic format
        f"{stadium_name} stadium, {country}",  # With 'stadium' keyword
        f"{stadium_name} arena, {country}",  # With 'arena' keyword
        f"{stadium_name} field, {country}",  # With 'field' keyword
    ]
    
    # Add city-based queries if city is provided
    if city:
        # Handle cases where city contains state/region
        city_parts = city.split(',')
        main_city = city_parts[0].strip()
        
        # Add queries with city
        queries.extend([
            f"{stadium_name}, {main_city}, {country}",
            f"{stadium_name} stadium, {main_city}, {country}",
            f"{stadium_name} arena, {main_city}, {country}"
        ])
        
        # If state/region is provided, add full location queries
        if len(city_parts) > 1:
            full_location = city.strip()
            queries.extend([
                f"{stadium_name}, {full_location}, {country}",
                f"{stadium_name} stadium, {full_location}, {country}"
            ])

    # Use Nominatim for geocoding with different query formats
    for query in queries:
        location = get_location_from_nominatim(query)
        if location:
            return location
    
    # If no results found with stadium name, try searching with city
    if city:
        city_queries = [
            f"{city}, {country}",
            main_city + f", {country}"
        ]
        
        for query in city_queries:
            location = get_location_from_nominatim(query)
            if location:
                return location
    
    return None