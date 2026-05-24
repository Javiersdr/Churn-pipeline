# Based on the airflow documentation tutorials
from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.bash import BashOperator
from airflow.operators.python import PythonOperator
import sys

sys.path.insert(0, '/opt/airflow/dbt_project')
# Now I also import my own ingestion script
from src.ingestion import run_ingestion

default_args = {
    'depends_on_past': False,
    'start_date': datetime(2021, 1, 1),
    'retries': 1,
    'retry_delay': timedelta(minutes=5),
}

def load_duckdb_from_minio():
    """Copia los datos ingeridos de MinIO a la tabla telco_churn en DuckDB."""
    import duckdb
    con = duckdb.connect('/opt/airflow/dbt_project/data/churn_data.duckdb')
    con.execute("INSTALL httpfs; LOAD httpfs;")
    con.execute("""
        SET s3_region='us-east-1';
        SET s3_endpoint='minio:9000';
        SET s3_url_style='path';
        SET s3_access_key_id='admin';
        SET s3_secret_access_key='password';
        SET s3_use_ssl=false;
    """)
    con.execute("""
        CREATE OR REPLACE TABLE main.telco_churn AS
        SELECT * FROM 's3://churn-data-lake/bronze/telco_churn/*.parquet'
    """)
    con.close()

with DAG(
    'churn_pipeline',
    default_args=default_args,
    description='Cloud-native churn pipeline: dlt, MinIO, DuckDB, dbt',
    schedule_interval='@daily',
    catchup=False,
    tags=['churn', 'dbt', 'dlt'],
) as dag:
    

    ingest_data = PythonOperator(
        task_id='dlt_ingest_to_minio',
        python_callable=run_ingestion,
    )

    load_duckdb = PythonOperator(
        task_id='load_duckdb_from_minio',
        python_callable=load_duckdb_from_minio,
    )

    dbt_run = BashOperator(
        task_id='dbt_run',
        bash_command='cd /opt/airflow/dbt_project/dbt_churn && dbt run',
    )

    dbt_test = BashOperator(
        task_id='dbt_test',
        bash_command='cd /opt/airflow/dbt_project/dbt_churn && dbt test',
    )

    ingest_data >> load_duckdb >> dbt_run >> dbt_test