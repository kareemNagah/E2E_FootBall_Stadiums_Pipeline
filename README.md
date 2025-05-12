docker-compose up --build

# to overcome Permission denied: 'data/stadiums_data_20250504_102232.csv' Error 
- mkdir -p /home/kareemngh/FootBallDataEngineering/data
- chmod -R 777 /home/kareemngh/FootBallDataEngineering/data 
- volumes: ./data:/opt/airflow/data:rw
