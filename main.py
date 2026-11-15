import functions_framework
from src.iconha_monitoring.pipeline import execute_pipeline


@functions_framework.http
def run_pipeline(request):
    """HTTP Entrypoint for Google Cloud Run Functions (2nd Gen)."""
    return execute_pipeline()


if __name__ == "__main__":
    execute_pipeline()