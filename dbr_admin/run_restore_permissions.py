import logging
import os
import sys

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def read_dbr_config(file_path):
    config = {}
    try:
        with open(file_path, 'r') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#') or '=' not in line:
                    continue
                key, value = line.split('=', 1)
                config[key.strip()] = value.strip()
    except Exception as e:
        logger.error(f"Error reading config file: {e}")
    return config

def main():
    # Determine the directory of this script
    script_dir = os.path.dirname(os.path.abspath(__file__))
    dbr_path = os.path.join(script_dir, 'dbr.txt')
    
    if not os.path.exists(dbr_path):
        logger.error(f"Config file not found: {dbr_path}")
        return

    config = read_dbr_config(dbr_path)
    host = config.get('host')
    token = config.get('token')

    if not host or not token:
        logger.error("Host or token not found in dbr.txt")
        return

    # clean host for restore_cluster_permissions (it expects no protocol)
    if host.startswith('https://'):
        host = host[8:]
    elif host.startswith('http://'):
        host = host[7:]

    # Import the function
    try:
        from .restore_cluster_permissions import restore_cluster_permissions
    except ImportError:
        try:
             # Fallback if not running as module (though restore_cluster_permissions might fail)
            from restore_cluster_permissions import restore_cluster_permissions
        except ImportError as e:
            logger.error(f"Failed to import restore_cluster_permissions: {e}")
            logger.info("Try running as module from parent directory: python -m dbr_admin.run_restore_permissions")
            return

    logger.info(f"Starting restore_cluster_permissions on host: {host}")
    restore_cluster_permissions(host, token, logger)

if __name__ == "__main__":
    main()
