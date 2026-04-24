import subprocess
import sys

# Let's define a function that runs every dbt command in dbt_churn or any other folder if indicated
def run_cmd(cmd, cwd="dbt_churn"):
    result = subprocess.run(cmd, shell=True, cwd=cwd, capture_output=True, text=True)
    print(result.stdout)
    if result.returncode != 0:
        print(f"Error ({result.returncode}): {result.stderr}")
        sys.exit(1)
    return True

if __name__ == "__main__":
    run_cmd("dbt deps")
    run_cmd("dbt seed")
    run_cmd("dbt run")
    run_cmd("dbt test")
    print("\nPipeline completed succesfully!")