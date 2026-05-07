# Based on the airflow documentation tutorials
from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.bash import BashOperator

default_args = {
    'depends_on_past': False,
    'start_date': datetime(2021, 1, 1),
    'retries': 1,
    'retry_delay': timedelta(minutes=5),
}

with DAG(
    'churn_pipeline',
    default_args=default_args,
    description='dbt churn pipeline',
    schedule_interval='@daily',
    catchup=False,
    tags=['churn', 'dbt'],
) as dag:
    

    dbt_seed = BashOperator(
        task_id='dbt_seed',
        bash_command='cd /opt/airflow/dbt_project/dbt_churn && dbt seed',
    )
    dbt_run = BashOperator(
        task_id='dbt_run',
        bash_command='cd /opt/airflow/dbt_project/dbt_churn && dbt run',
    )

    dbt_test = BashOperator(
        task_id='dbt_test',
        bash_command='cd /opt/airflow/dbt_project/dbt_churn && dbt test',
    )

    dbt_seed >> dbt_run >> dbt_test