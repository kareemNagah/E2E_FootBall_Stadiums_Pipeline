import os 
import sys
from airflow import DAG 
from airflow.operators.python import PythonOperator
from datetime import datetime, timedelta
import pandas as pd
import json
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Add the parent directory to the path so we can import from pipelines
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pipelines.wikipedia_pipeline import extract_wikipedia_data , transform_wikipedia_data , write_wikipedia_data

# Define default arguments for the DAG
default_args = {
    "owner": "Kareem Nagah",
    "depends_on_past": False,
    "email_on_failure": False,
    "email_on_retry": False,
    "start_date": datetime(2025, 5, 2)
}

# Create the DAG
dag = DAG(
    dag_id="wikipedia_football_stadiums_etl",
    default_args=default_args,
    description="ETL pipeline for football stadiums data from Wikipedia",
    schedule_interval="@weekly",  # Run once a week
    catchup=False
)


# Define the tasks
extract_data = PythonOperator(
    task_id='extract_data',
    python_callable=extract_wikipedia_data,
    op_kwargs={'url': 'https://en.wikipedia.org/wiki/List_of_association_football_stadiums_by_capacity'},
    dag=dag
)

transform_data = PythonOperator(
    task_id='transform_data',
    python_callable=transform_wikipedia_data,
    provide_context=True,
    dag=dag
)

load_data = PythonOperator(
    task_id='write_wikipedia_data',
    python_callable=write_wikipedia_data,
    provide_context=True,
    dag=dag
)

# Set task dependencies
extract_data >> transform_data >> load_data