import os
import requests
import folium
from dotenv import load_dotenv
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut
import pygris
import geopandas as gpd
from shapely.geometry import Point
import matplotlib.pyplot as plt

class GeocodingMap:
    def __init__(self):
        load_dotenv()
        self.access_token = os.getenv("MAPBOX_ACCESS_TOKEN")
        
        if not self.access_token:
            raise ValueError("Mapbox access token not found in environment variables")
        
        self.geolocator = Nominatim(user_agent="my_agent")

    def get_location_info(self, latitude, longitude):
        try:
            location = self.geolocator.reverse(f"{latitude}, {longitude}")
            address = location.raw['address']
            
            county = address.get('county', '')
            state = address.get('state', '')
            
            return county, state
        except GeocoderTimedOut:
            print("The geocoding service timed out. Please try again.")
            return None, None

    def geocode_address(self, address):
        base_url = "https://api.mapbox.com/geocoding/v5/mapbox.places/"
        url = f"{base_url}{address}.json?access_token={self.access_token}"
        
        response = requests.get(url)
        
        if response.status_code == 200:
            data = response.json()
            if data['features']:
                coordinates = data['features'][0]['center']
                return {
                    'longitude': coordinates[0],
                    'latitude': coordinates[1]
                }
            else:
                return None
        else:
            print(f"Error: {response.status_code}")
            return None

    def get_block_group_data(self, state, county):
        try:
            bg_data = pygris.block_groups(state=state, county=county, year=2022, cb=True)
            return bg_data
        except Exception as e:
            print(f"Error fetching block group data: {e}")
            return None

    def create_buffer_and_clip(self, latitude, longitude, block_group_data, buffer_miles=3):
        # Create a point from the lat/lon
        point = Point(longitude, latitude)
        
        # Create a GeoDataFrame with the point
        point_gdf = gpd.GeoDataFrame(geometry=[point], crs="EPSG:4326")
        
        # Reproject to a projected CRS for accurate buffer
        point_projected = point_gdf.to_crs(epsg=3857)
        
        # Create buffer (3 miles = 4828.03 meters)
        buffer = point_projected.buffer(4828.03)
        
        # Reproject buffer back to WGS84
        buffer_wgs84 = buffer.to_crs(epsg=4326)
        
        # Clip block groups with buffer
        clipped_bg = gpd.clip(block_group_data, buffer_wgs84)
        
        return clipped_bg, buffer_wgs84

    def plot_clipped_map(self, latitude, longitude, address, county, state, clipped_bg, buffer):
        # Create a base map
        m = folium.Map(location=[latitude, longitude], zoom_start=12)

        # Add marker for the address
        popup_text = f"{address}<br>County: {county}<br>State: {state}"
        folium.Marker(
            [latitude, longitude],
            popup=popup_text,
            tooltip=address
        ).add_to(m)

        # Add clipped block group boundaries
        folium.GeoJson(
            clipped_bg,
            style_function=lambda feature: {
                'fillColor': 'blue',
                'color': 'black',
                'weight': 2,
                'fillOpacity': 0.1,
            }
        ).add_to(m)

        # Add buffer
        folium.GeoJson(
            buffer,
            style_function=lambda feature: {
                'fillColor': 'red',
                'color': 'red',
                'weight': 2,
                'fillOpacity': 0.1,
            }
        ).add_to(m)

        m.save("clipped_map.html")
        print("Map saved as 'clipped_map.html'")

    def process_address(self, address):
        result = self.geocode_address(address)

        if result:
            latitude = result['latitude']
            longitude = result['longitude']
            print(f"Coordinates for {address}:")
            print(f"Latitude: {latitude}")
            print(f"Longitude: {longitude}")
            
            county, state = self.get_location_info(latitude, longitude)
            if county and state:
                print(f"County: {county}")
                print(f"State: {state}")
                
                block_group_data = self.get_block_group_data(state, county)
                if block_group_data is not None:
                    print("Successfully retrieved block group data.")
                    
                    clipped_bg, buffer = self.create_buffer_and_clip(latitude, longitude, block_group_data)
                    print("Created buffer and clipped block group data.")
                    
                    self.plot_clipped_map(latitude, longitude, address, county, state, clipped_bg, buffer)
                else:
                    print("Failed to retrieve block group data.")
            else:
                print("Couldn't retrieve county and state information.")
        else:
            print("Geocoding failed or no results found.")

# Example usage
if __name__ == "__main__":
    try:
        geocoding_map = GeocodingMap()
        address = input("Please enter an address: ")
        geocoding_map.process_address(address)
    except ValueError as e:
        print(f"Error: {e}")