import os
from dotenv import load_dotenv
from openai import OpenAI
import json
import pandas as pd
from pygris.data import get_census

class CensusDataFetcher:
    def __init__(self, variables_file='acs5_variables.csv'):
        load_dotenv()
        self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        self.df = pd.read_csv(variables_file)

    def comprehensive_census_agent(self, user_request, state_name, county_name):
        prompt = f"""
        Analyze the following user request for census data: "{user_request}"
        The state is {state_name} and the county is {county_name}.

        1. Determine FIPS Codes:
        Provide the FIPS codes for the given state and county.

        2. Interpret Census Variables:
        Based on the user request, determine the appropriate census variable code(s).
        Here are the available census variables:
        {self.df.to_string(index=False)}

        3. Translate Geography:
        Translate the geography information into the correct format.
        The "for" parameter should be the geographic unit (e.g., county, tract, block group).

        4. Extract Year and Dataset:
        Determine the year and dataset (e.g., acs/acs5) from the user request.

        Provide the output as a JSON object with the following structure:
        {{
            "state_fips": "XX",
            "county_fips": "YYY",
            "variables": [list of variable codes],
            "geography": {{
                "for": "geographic unit"
            }},
            "year": "YYYY",
            "dataset": "dataset name"
        }}
        where XX is the 2-digit state FIPS code and YYY is the 3-digit county FIPS code.

        If any information is not provided or cannot be determined, use "null" for that field.
        """

        response = self.client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a comprehensive assistant that interprets census data requests, provides FIPS codes, translates geographic information, and extracts relevant details."},
                {"role": "user", "content": prompt}
            ],
            temperature=0,
        )

        content = response.choices[0].message.content.strip()
        
        try:
            json_start = content.find('{')
            json_end = content.rfind('}') + 1
            json_str = content[json_start:json_end]
            result = json.loads(json_str)
        except json.JSONDecodeError:
            result = {"error": "Failed to parse response", "raw_response": content}
        
        return result

    def get_census_parameters(self, user_request, state_name, county_name):
        result = self.comprehensive_census_agent(user_request, state_name, county_name)
        
        dataset = result.get('dataset')
        variables = result.get('variables')
        year = result.get('year')
        geography = result.get('geography', {})
        state_fips = result.get('state_fips')
        county_fips = result.get('county_fips')
        
        params = {
            "for": geography.get('for'),
            "in": f"state:{state_fips} county:{county_fips}"
        }
        
        return dataset, variables, year, params

    def fetch_census_data(self, dataset, variables, year, params):
        try:
            data = get_census(dataset=dataset,
                              variables=variables,
                              year=year,
                              params=params,
                              return_geoid=True,
                              guess_dtypes=True)
            return data
        except Exception as e:
            print(f"Error fetching census data: {str(e)}")
            return None

    def process_request(self, user_request, state_name, county_name):
        dataset, variables, year, params = self.get_census_parameters(user_request, state_name, county_name)
        
        print("Census API Parameters:")
        print(f"Dataset: {dataset}")
        print(f"Variables: {variables}")
        print(f"Year: {year}")
        print(f"Params: {params}")
        
        census_data = self.fetch_census_data(dataset, variables, year, params)
        
        if census_data is not None:
            print("\nFetched Census Data:")
            print(census_data.head())
            return census_data
        else:
            print("\nFailed to fetch census data.")
            return None

# Example usage
if __name__ == "__main__":
    fetcher = CensusDataFetcher()
    user_request = 'I want to download the total population and median household income data for block groups in 2021'
    state_name = 'Texas'
    county_name = 'Harris County'
    fetcher.process_request(user_request, state_name, county_name)