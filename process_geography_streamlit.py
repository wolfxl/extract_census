import os
import requests
import folium
import streamlit as st
from dotenv import load_dotenv
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut
import pygris
import geopandas as gpd
from shapely.geometry import Point
import matplotlib.pyplot as plt
from streamlit_folium import folium_static

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
            st.error("The geocoding service timed out. Please try again.")
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
            st.error(f"Error: {response.status_code}")
            return None

    def get_block_group_data(self, state, county):
        try:
            bg_data = pygris.block_groups(state=state, county=county)
            return bg_data
        except Exception as e:
            st.error(f"Error fetching block group data: {e}")
            return None

    def create_buffer_and_clip(self, latitude, longitude, block_group_data, buffer_miles=3):
        point = Point(longitude, latitude)
        point_gdf = gpd.GeoDataFrame(geometry=[point], crs="EPSG:4326")
        point_projected = point_gdf.to_crs(epsg=3857)
        buffer = point_projected.buffer(4828.03)  # 3 miles in meters
        buffer_wgs84 = buffer.to_crs(epsg=4326)
        clipped_bg = gpd.clip(block_group_data, buffer_wgs84)
        return clipped_bg, buffer_wgs84

    def create_map(self, latitude, longitude, address, county, state, clipped_bg, buffer):
        m = folium.Map(location=[latitude, longitude], zoom_start=12)

        popup_text = f"{address}<br>County: {county}<br>State: {state}"
        folium.Marker(
            [latitude, longitude],
            popup=popup_text,
            tooltip=address
        ).add_to(m)

        folium.GeoJson(
            clipped_bg,
            style_function=lambda feature: {
                'fillColor': 'blue',
                'color': 'black',
                'weight': 2,
                'fillOpacity': 0.1,
            }
        ).add_to(m)

        folium.GeoJson(
            buffer,
            style_function=lambda feature: {
                'fillColor': 'red',
                'color': 'red',
                'weight': 2,
                'fillOpacity': 0.1,
            }
        ).add_to(m)

        return m

    def process_address(self, address):
        result = self.geocode_address(address)

        if result:
            latitude = result['latitude']
            longitude = result['longitude']
            st.write(f"Coordinates for {address}:")
            st.write(f"Latitude: {latitude}")
            st.write(f"Longitude: {longitude}")
            
            county, state = self.get_location_info(latitude, longitude)
            if county and state:
                st.write(f"County: {county}")
                st.write(f"State: {state}")
                
                block_group_data = self.get_block_group_data(state, county)
                if block_group_data is not None:
                    st.success("Successfully retrieved block group data.")
                    
                    clipped_bg, buffer = self.create_buffer_and_clip(latitude, longitude, block_group_data)
                    st.success("Created buffer and clipped block group data.")
                    
                    map = self.create_map(latitude, longitude, address, county, state, clipped_bg, buffer)
                    folium_static(map)
                else:
                    st.error("Failed to retrieve block group data.")
            else:
                st.error("Couldn't retrieve county and state information.")
        else:
            st.error("Geocoding failed or no results found.")

def main():
    st.title("Address Geocoding and Block Group Mapping")
    
    try:
        geocoding_map = GeocodingMap()
        
        address = st.text_input("Please enter an address:")
        
        if st.button("Process Address"):
            if address:
                geocoding_map.process_address(address)
            else:
                st.warning("Please enter an address.")
    
    except ValueError as e:
        st.error(f"Error: {e}")

if __name__ == "__main__":
    main()



    