import os
import sys
import json

def generate_index(parent_dir):
    for subdir in os.listdir(parent_dir):
        subdir_path = os.path.join(parent_dir, subdir)
        if os.path.isdir(subdir_path):
            files = [f for f in os.listdir(subdir_path) if os.path.isfile(os.path.join(subdir_path, f))]
            total_size = sum(os.path.getsize(os.path.join(subdir_path, f)) for f in files)
            total_size_mb = total_size / (1024 * 1024)
            
            index_data = {
                'date': subdir,
                'file_count': len(files),
                'total_size_mb': round(total_size_mb, 2),
                'filenames': files
            }
            
            index_file_path = os.path.join(subdir_path, 'index.json')
            with open(index_file_path, 'w') as f:
                json.dump(index_data, f, indent=4)
            print(f"Generated index for {subdir_path}")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python generate_index.py <parent_directory>")
        sys.exit(1)
        
    parent_directory = sys.argv[1]
    generate_index(parent_directory)
