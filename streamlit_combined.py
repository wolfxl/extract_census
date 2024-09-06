import os
import streamlit as st
from dotenv import load_dotenv
from train_of_thought_comprehensive_agent_with_latlon import CensusDataFetcher
from process_geography import GeocodingMap
import geopandas as gpd
import folium
from shapely.geometry import Point
from streamlit_folium import folium_static
import plotly.graph_objects as go
import plotly.express as px

class CombinedCensusMap:
    def __init__(self):
        load_dotenv()
        self.census_fetcher = CensusDataFetcher()
        self.geocoding_map = GeocodingMap()

    def process_request(self, address, census_request):
        # Step 3: Geocode the address and get state and county
        result = self.geocoding_map.geocode_address(address)
        if not result:
            st.error("Failed to geocode the address.")
            return None

        latitude, longitude = result['latitude'], result['longitude']
        county, state = self.geocoding_map.get_location_info(latitude, longitude)
        if not county or not state:
            st.error("Failed to get county and state information.")
            return None

        st.write(f"Address: {address}")
        st.write(f"County: {county}")
        st.write(f"State: {state}")

        # Step 4: Get the TIGER boundary data
        block_group_data = self.geocoding_map.get_block_group_data(state, county)
        if block_group_data is None:
            st.error("Failed to retrieve block group data.")
            return None

        # Step 5: Get the census variable data
        census_data = self.census_fetcher.process_request(census_request, state, county)
        if census_data is None:
            st.error("Failed to fetch census data.")
            return None

        # Step 6: Merge the variables with the geopandas boundary
        # Ensure both DataFrames have a 'GEOID' column
        if 'GEOID' not in block_group_data.columns:
            st.error("Error: 'GEOID' column not found in block_group_data")
            return None
        if 'GEOID' not in census_data.columns:
            st.error("Error: 'GEOID' column not found in census_data")
            return None

        merged_data = block_group_data.merge(census_data, on='GEOID', how='left')

        # Ensure the CRS is set to EPSG:4326 (WGS84)
        merged_data = merged_data.to_crs(epsg=4326)

        return latitude, longitude, county, state, merged_data

    def create_buffer_and_clip(self, latitude, longitude, data, buffer_miles=5):
        # Create a point from the lat/lon
        point = Point(longitude, latitude)
        
        # Create a GeoDataFrame with the point
        point_gdf = gpd.GeoDataFrame(geometry=[point], crs="EPSG:4326")
        
        # Ensure the input data is in EPSG:4326
        data = data.to_crs(epsg=4326)
        
        # Reproject to a projected CRS for accurate buffer
        point_projected = point_gdf.to_crs(epsg=3857)
        
        # Create buffer (5 miles = 8046.72 meters)
        buffer = point_projected.buffer(8046.72)
        
        # Reproject buffer back to WGS84
        buffer_wgs84 = buffer.to_crs(epsg=4326)
        
        # Clip data with buffer
        clipped_data = gpd.clip(data, buffer_wgs84)
        
        return clipped_data, buffer_wgs84

    def plot_map(self, latitude, longitude, address, county, state, merged_data):
        # Create buffer and clip data
        clipped_data, buffer = self.create_buffer_and_clip(latitude, longitude, merged_data)

        # Create a base map with gray tiles
        m = folium.Map(location=[latitude, longitude], zoom_start=12, 
                       tiles='CartoDB positron', 
                       attr='CartoDB')  # 'CartoDB positron' is a light gray basemap

        # Add marker for the address
        popup_text = f"{address}<br>County: {county}<br>State: {state}"
        folium.Marker(
            [latitude, longitude],
            popup=popup_text,
            tooltip=address
        ).add_to(m)

        # Add choropleth layer for clipped data
        variable_name = clipped_data.columns[-1]  # Assume the last column is the census variable
        choropleth = folium.Choropleth(
            geo_data=clipped_data.to_json(),
            name='Census Data',
            data=clipped_data,
            columns=['GEOID', variable_name],
            key_on='feature.properties.GEOID',
            fill_color='YlOrRd',
            fill_opacity=0.7,
            line_opacity=0.2,
            legend_name=variable_name
        ).add_to(m)

        # Add popups to the choropleth layer
        choropleth.geojson.add_child(
            folium.features.GeoJsonTooltip(
                fields=['GEOID', variable_name],
                aliases=['Block Group ID:', f'{variable_name}:'],
                style=("background-color: white; color: #333333; font-family: arial; font-size: 12px; padding: 10px;")
            )
        )

        # Add buffer outline
        folium.GeoJson(
            buffer.to_json(),
            style_function=lambda feature: {
                'fillColor': 'none',
                'color': 'red',
                'weight': 2,
            },
            name='5-Mile Buffer'
        ).add_to(m)

        folium.LayerControl().add_to(m)

        # Fit the map to the buffer bounds
        m.fit_bounds(buffer.total_bounds.tolist())

        return m
    
    def plot_histogram(self, data, variable_name):
        fig = px.histogram(data, x=variable_name, nbins=20,
                           title=f'Distribution of {variable_name}')
        fig.update_layout(
            xaxis_title=variable_name,
            yaxis_title='Frequency',
            bargap=0.1
        )
        return fig

def main():
    st.title("Discover Your Neighborhood's Demographics")

    st.write("""
    This app allows you to explore demographic data for any location in the United States. 
    Simply enter an address and specify the census data you're interested in. 
    The app will generate a map showing the requested information for the area within a 5-mile radius of the address.
    """)

    combined_census_map = CombinedCensusMap()

    # User input
    address = st.text_input("Enter an address:")
    census_request = st.text_input("Enter your census data request:")

    if st.button("Generate Map"):
        with st.spinner("Processing request..."):
            result = combined_census_map.process_request(address, census_request)
            
            if result:
                latitude, longitude, county, state, merged_data = result
                st.success("Data processed successfully!")

                # Create and display the map
                m = combined_census_map.plot_map(latitude, longitude, address, county, state, merged_data)
                folium_static(m)

                # Display interactive histogram
                st.subheader("Data Distribution")
                variable_name = merged_data.columns[-1]  # Assume the last column is the census variable
                fig = combined_census_map.plot_histogram(merged_data, variable_name)
                st.plotly_chart(fig, use_container_width=True)

                # Optional: Display basic statistics
                st.subheader("Basic Statistics")
                st.write(merged_data[variable_name].describe())

if __name__ == "__main__":
    main()