# script created by GPT to export all Databricks User's workspace files.
# Files larger than 1 MB are not exported.
#  Noam 2025-01-07
#
#
import os
import requests
import dotenv
import logging

dotenv.load_dotenv()

# Logger configuration
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Configuration
DATABRICKS_URL = os.getenv("DATABRICKS_HOST")
TOKEN = os.getenv("DATABRICKS_TOKEN")
ROOT_DIR = "/Users"
BACKUP_DIR = "./databricks_backup"
MAX_FILE_SIZE_BYTES = 1 * 1024 * 1024  # 1 MB

if not TOKEN:
    raise ValueError("Environment variable DATABRICKS_TOKEN is not set")

if not DATABRICKS_URL:
    raise ValueError("Environment variable DATABRICKS_URL is not set")

if not DATABRICKS_URL.startswith("http"):
    DATABRICKS_URL = "https://" + DATABRICKS_URL


headers = {"Authorization": f"Bearer {TOKEN}"}

def list_workspace_objects(path):
    """List all objects (files and directories) in the Databricks workspace at the given path."""
    url = f"{DATABRICKS_URL}/api/2.0/workspace/list"
    logger.debug(f"Listing workspace objects at path: {path}")
    try:
        response = requests.request(
            "GET",
            url,
            headers=headers,
            data=f'{{"path": "{path}"}}',  # Include data in the body. NON STANDARD!
        )
        response.raise_for_status()
        return response.json().get("objects", [])
    except requests.exceptions.RequestException as e:
        logger.error(f"Error listing workspace objects at {path}: {e}")
        return []

def get_file_status(file_path):
    """Get the status of a file in Workspace, including its size."""
    url = f"{DATABRICKS_URL}/api/2.0/workspace/get-status"
    try:
        response = requests.get(url, headers=headers, params={"path": file_path})
        if response.status_code == 404:
            logger.warning(f"File {file_path} not found.")
            return None
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        logger.error(f"Error getting file status for {file_path}: {e}")
        return None

def export_notebook(notebook_path, local_path):
    """Export a notebook from Databricks to the local filesystem."""
    url = f"{DATABRICKS_URL}/api/2.0/workspace/export"
    try:
        response = requests.get(url, headers=headers, params={"path": notebook_path, "format": "SOURCE"})
        response.raise_for_status()
        os.makedirs(os.path.dirname(local_path), exist_ok=True)
        with open(local_path, "wb") as f:
            f.write(response.content)
        logger.info(f"Exported: {notebook_path} -> {local_path}")
    except requests.exceptions.RequestException as e:
        logger.error(f"Error exporting notebook {notebook_path}: {e}")

def backup_workspace(path, local_dir):
    """Recursively back up the Databricks workspace."""
    objects = list_workspace_objects(path)
    for obj in objects:
        object_type = obj["object_type"]
        object_path = obj["path"]
        local_path = os.path.join(local_dir, os.path.relpath(object_path, ROOT_DIR))

        if object_type == "DIRECTORY":
            os.makedirs(local_path, exist_ok=True)
            backup_workspace(object_path, local_dir)  # Recurse into the directory

        elif object_type == "NOTEBOOK":
            status = get_file_status(object_path)
            if status:
                if status.get("file_size", 0) <= MAX_FILE_SIZE_BYTES:
                    export_notebook(object_path, local_path + ".py")
                    #print(f"FAKE exporting {object_path}")
                else:
                    logger.warning(f"Skipping large file: {object_path} ({status['file_size']} bytes)")
            else:
                logger.warning(f"Skipping {object_path} - no status")

if __name__ == "__main__":
    try:
        os.makedirs(BACKUP_DIR, exist_ok=True)
        backup_workspace(ROOT_DIR, BACKUP_DIR)
        logger.info("Backup completed successfully.")
    except Exception as e:
        logger.critical(f"Unexpected error: {e}")
