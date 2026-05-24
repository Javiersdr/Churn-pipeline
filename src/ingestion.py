import dlt
from dlt.destinations import filesystem

BUCKET_URL = "s3://churn-data-lake"

@dlt.resource(name="telco_churn", write_disposition="merge", primary_key="customerID")
def get_customers():
    import csv
    import os
    csv_path = os.path.join(os.path.dirname(__file__), "..", "data", "raw", "WA_Fn-UseC_-Telco-Customer-Churn.csv")
    with open(csv_path, "r") as f:
        reader = csv.DictReader(f)
        for row in reader:
            yield row

def run_ingestion():
    pipeline = dlt.pipeline(
        pipeline_name="churn_ingestion",
        destination=filesystem(destination_name="bronze"),
        dataset_name="telco"
    )
    load_info = pipeline.run(get_customers())
    print(load_info)
    return load_info

if __name__ == "__main__":
    run_ingestion()