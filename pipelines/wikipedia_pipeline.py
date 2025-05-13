import os
import requests
import json
import pandas as pd
import requests
from datetime import datetime
from lxml import html
from io import StringIO
from pipelines.geocoding import get_stadium_location
from azure.storage.blob import  BlobClient

from dotenv import load_dotenv 
load_dotenv()


def get_wikipedia_page(url: str):
    headers = {'User-Agent': 'Mozilla/5.0 (compatible; KareemBot/1.0)'}
    print("Loading wikipedia page...", url)

    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        return response.content
    except requests.RequestException as e:
        print(f"An error occurred: {e}")
        return None



def extract_wikipedia_data(**kwargs):
    try:
        url = kwargs['url']
        print(f"Starting extraction from {url}")
        
       
        content = get_wikipedia_page(url)
        if not content:
            raise ValueError(f"Failed to retrieve content from {url}")
        
        tree = html.fromstring(content)

        # Find the table containing stadium data 
        tables = tree.xpath('//table[contains(@class, "wikitable")]')
        if len(tables) < 2:
            raise ValueError(f"Expected at least 2 wikitables, but found {len(tables)}")
            
        table = tables[1]  
        
      
        rows = table.xpath('.//tr')[1:]  
        if not rows:
            raise ValueError("No data rows found in the table")
            
        print(f"Found {len(rows)} stadium entries to process")
        
        data = {
            'stadiums': [],
            'capacity': [],
            'region': [],
            'country': [],
            'city': []
        }
        
        for i, row in enumerate(rows):
            try:
                
                stadium = row.xpath('./td[1]//a/text()')
                stadium_name = stadium[0] if stadium else None
                
                # Skip rows with no stadium name
                if not stadium_name:
                    print(f"Warning: Row {i+1} has no stadium name, skipping")
                    continue
                    
                data['stadiums'].append(stadium_name)
                
                capacity = row.xpath('./td[2]/text()')
                capacity_value = capacity[0].strip() if capacity else None
                data['capacity'].append(capacity_value)
                
                region = row.xpath('./td[3]/text()')
                data['region'].append(region[0].strip() if region else None)
                    
                country = row.xpath('./td[4]/text()[normalize-space()] | ./td[4]//a/text()')
                data['country'].append(country[0].strip() if country else None)

                city = row.xpath('./td[5]/text()[normalize-space()] | ./td[5]//a/text()')
                data['city'].append(city[0].strip() if city else None)
            except Exception as e:
                print(f"Error processing row {i+1}: {e}")
        
        # Validate extracted data
        if not data['stadiums']:
            raise ValueError("No stadium data was extracted")
            
        print(f"Successfully extracted data for {len(data['stadiums'])} stadiums")
        
        
        df = pd.DataFrame(data)
        
        # Clean data - remove rows with missing essential data
        missing_data = df['stadiums'].isna() | df['capacity'].isna() | df['country'].isna()
        if missing_data.any():
            print(f"Removing {missing_data.sum()} rows with missing essential data")
            df = df[~missing_data]
        
        current_time = datetime.now().strftime("%Y%m%d")
        
        # Ensure data directory exists in Airflow home
        data_dir = os.path.join(os.getenv('AIRFLOW_HOME', '/opt/airflow'), 'data')
        os.makedirs(data_dir, exist_ok=True)
        
        # Save raw data
        raw_file_path = os.path.join(data_dir, f"raw_stadiums_data_{current_time}.csv")
        df.to_csv(raw_file_path, index=False)
        print(f"Raw data saved to {raw_file_path}")
        
        # Push to XCom for next task
        json_rows = json.loads(df.to_json(orient='records'))
        kwargs['ti'].xcom_push(key='row_stadiums_data', value=json_rows)
        
        return f"Successfully extracted {len(df)} stadium records"
    except Exception as e:
        print(f"Error in extract_wikipedia_data: {e}")
        raise

# Use the geocoding module 
def get_stadium_lat_long(country, stadium_name, city=None):
    
    return get_stadium_location(country, stadium_name, city)




def transform_wikipedia_data(**kwargs):
    try:
        data = kwargs['ti'].xcom_pull(key='row_stadiums_data', task_ids='extract_data')
        
        if not data:
            print("Warning: No stadium data received from extract task")
            return "No data to transform"
        
        print(f"Starting transformation of {len(data)} stadium records")
        df = pd.DataFrame(data)
        
        # Clean and transform data
        df['capacity'] = df['capacity'].str.replace(',', '').astype(int)
        df['city'] = df['city'].str.replace(', ',' - ')
        
        # Create a copy of the original stadium names for reference
        df['original_stadium_name'] = df['stadiums']
        
        # Get locations for all stadiums with improved geocoding
        print("Starting primary geocoding process...")
        locations = []

    
        for _ , row in df.iterrows():
            try:
                location = get_stadium_lat_long(row['country'], row['stadiums'], row['city'])
                locations.append(location)
                if location:
                    print(f"✓ Found location for {row['stadiums']}")
                else:
                    print(f"⚠️ No location found for {row['stadiums']} in {row['country']}")
            except Exception as e:
                print(f"❌ Error geocoding {row['stadiums']}: {e}")
                locations.append(None)
        
        df['location'] = locations
        df['lat'] = df['location'].apply(lambda x: x[0] if x else None)
        df['lon'] = df['location'].apply(lambda x: x[1] if x else None)
        
        # Try alternative queries for stadiums that couldn't be found
        mask = df['location'].isna()
        if mask.any():
            print(f"Attempting alternative geocoding for {mask.sum()} stadiums...")
            # Try with region information if available
            for idx, row in df[mask].iterrows():
                try:
                    # Try with region if available
                    region = row['region'] if pd.notna(row['region']) else row['country']
                    location = get_stadium_lat_long(region, row['stadiums'], row['city'])
                    
                    # If still not found, try with a simplified stadium name (remove common words)
                    if not location and ' ' in row['stadiums']:
                        simplified_name = row['stadiums']
                        for word in ['Stadium', 'Arena', 'Park', 'Complex', 'Centre', 'Center']:
                            simplified_name = simplified_name.replace(f" {word}", "")
                        
                        location = get_stadium_lat_long(row['country'], simplified_name, row['city'])
                        
                    df.at[idx, 'location'] = location
                    
                    if location:
                        print(f"✓ Found location for {row['stadiums']} using alternative method")
                except Exception as e:
                    print(f"❌ Error in alternative geocoding for {row['stadiums']}: {e}")
        
        # Fill remaining None values with a default message
        missing_count = df['location'].isna().sum()
        df['location'] = df['location'].fillna('Location not found')
        
        # for Log 
        print(f"Geocoding complete: {len(df) - missing_count}/{len(df)} locations found ({(len(df) - missing_count) / len(df) * 100:.1f}%)")
        
        # push to xcom 
        # Using orient='records' to create a list of dictionaries that pandas can parse back


        json_data = df.to_json(orient='records')
        kwargs['ti'].xcom_push(key='transformed_data', value=json_data)
        
        return "Done"
    except Exception as e:
        print(f"Error in transform_wikipedia_data: {e}")
        raise




def write_wikipedia_data(**kwargs):
    try:
        data = kwargs['ti'].xcom_pull(key='transformed_data', task_ids='transform_data')
        
        if not data:
            print("Warning: No transformed data received from previous task")
            return "No data to write"
        
        # Parse the JSON string back into a Python object before creating DataFrame
        if isinstance(data, str):
            try:
                data = json.loads(data)
            except json.JSONDecodeError as e:
                print(f"Error decoding JSON data: {e}")
                print(f"Data type: {type(data)}")
                print(f"Data preview: {data[:100]}..." if isinstance(data, str) and len(data) > 100 else f"Data: {data}")
                raise
        
        # Validate data structure before creating DataFrame
        if not isinstance(data, list) or not data:
            print(f"Invalid data structure: expected non-empty list, got {type(data)}")
            print(f"Data preview: {str(data)[:100]}..." if len(str(data)) > 100 else f"Data: {data}")
            raise ValueError("DataFrame constructor not properly called: data must be a non-empty list of dictionaries")
            
        df = pd.DataFrame(data)
        current_time = datetime.now().strftime("%Y%m%d %H:%M:%S")
        data_dir = os.path.join(os.getenv('AIRFLOW_HOME', '/opt/airflow'), 'data')
        os.makedirs(data_dir, exist_ok=True)
        
        # Save both CSV and JSON formats
        # csv_path = os.path.join(data_dir, f"cleaned_stadiums_data_{current_time}.csv")
        # json_path = os.path.join(data_dir, f"cleaned_stadiums_data_{current_time}.json")
        
        # df.to_csv(csv_path, index=False)
        # df.to_json(json_path, orient='records', indent=2)
        
        # Save to Azure Blob Storage
        # Convert DataFrame to CSV string and upload to Azure Blob Storage

        csv_buffer = StringIO()  
        df.to_csv(csv_buffer, index=False)
        csv_data = csv_buffer.getvalue()
        
        sas_key = os.getenv("AZURE_SAS_KEY")
        sas_url= f'https://footballstorage.blob.core.windows.net/footballde/Data/cleaned_stadiums_data_{current_time}.csv' + sas_key
    
        blob_client = BlobClient.from_blob_url(sas_url)
        blob_client.upload_blob(csv_data, overwrite=True)
        
        #print(f"Successfully saved data to {csv_path} and {json_path}")
        print(f"Total stadiums processed: {len(df)}")
        print(f"Stadiums with locations found: {df['location'].notna().sum()}")
        
        return "Done"
    
    except Exception as e:
        print(f"Error in write_wikipedia_data: {e}")
        raise
