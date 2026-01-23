import json
import os
from pathlib import Path

# gemini 2026-01-18 13:30
# This script processes the Terraform output to create individual .env files for student groups.

def generate_env_files():
    # 1. Configuration
    json_input = "all_groups.json"
    output_dir = Path("dist/student_envs")
    
    # Ensure output directory exists
    output_dir.mkdir(parents=True, exist_ok=True)

    # 2. Check if input file exists
    if not os.path.exists(json_input):
        print(f"Error: {json_input} not found.")
        print("Run: terraform output -json sp_credentials_and_env_vars > all_groups.json")
        return

    # 3. Load Terraform output
    try:
        with open(json_input, "r") as f:
            data = json.load(f)
    except Exception as e:
        print(f"Error parsing JSON: {e}")
        return

    print(f"Processing {len(data)} groups...")

    # 4. Generate files
    for group_key, env_vars in data.items():
        # group_key is "01", "02", etc.
        filename = output_dir / f"group_{group_key}.env"
        
        with open(filename, "w") as f:
            f.write(f"# Databricks Environment for Group {group_key}\n")
            f.write("# Generated for IEM Teaching Lab\n\n")
            
            for key, value in env_vars.items():
                # Handle the missing secret case
                if key == "DATABRICKS_CLIENT_SECRET" and (not value or value == ""):
                    f.write(f"{key}=INSERT_MANUALLY_FROM_UI_SETTINGS\n")
                else:
                    f.write(f"{key}={value}\n")
        
        print(f" Created: {filename}")

    print("\nDone! Individual .env files are in the 'dist/student_envs' folder.")

if __name__ == "__main__":
    generate_env_files()
