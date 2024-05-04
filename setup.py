import sys

import requests
import tarfile
import os
import shutil


def clean_directory_except(base_path, keep_patterns):
    """ Remove all subdirectories in the base_path except the keep_patterns """
    try:
        os.stat(base_path)
    except Exception as e:
        print(f"{base_path}: ", e)
    for subdir in os.listdir(base_path):
        full_path = os.path.join(base_path, subdir)
        if os.path.isdir(full_path) and not any(full_path.endswith(pattern) for pattern in keep_patterns):
            shutil.rmtree(full_path)
        elif not any(full_path.endswith(pattern) for pattern in keep_patterns):
            os.remove(full_path)


print("Clean src")
clean_directory_except('./src', ['ph', 'extension.py', 'ads1x15.py'])
print("Clean scripts")
clean_directory_except('./scripts', ["_skip"])
print("Clean boards")
clean_directory_except('./boards', ["_skip"])

# Download the archive
url = "https://github.com/telenkov88/reefrhythm-smartdoser/archive/refs/tags/latest.tar.gz"
response = requests.get(url)

# Save the downloaded content to a .tar.gz file
archive_path = 'latest.tar.gz'
with open(archive_path, 'wb') as file:
    file.write(response.content)

# Extract specific folders from the archive
with tarfile.open(archive_path, "r:gz") as tar:
    members = tar.getmembers()
    # Modify the path and extract 'src' and 'scripts' directories
    for member in members:
        if member.name.startswith("reefrhythm-smartdoser-latest/src") or \
                member.name.startswith("reefrhythm-smartdoser-latest/scripts") or \
                member.name.startswith("reefrhythm-smartdoser-latest/boards"):
            member.name = '/'.join(member.name.split('/')[1:])  # Remove the first directory from the path
            tar.extract(member, path='.')

os.remove("latest.tar.gz")
