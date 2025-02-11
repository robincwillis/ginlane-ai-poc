import os


def remove_ds_store(root_dir):
  """
  Walk through the directories and remove all .DS_Store files.

  Args:
      root_dir (str): The root directory to start the search.
  """
  for dirpath, _, files in os.walk(root_dir):
    for file in files:
      if file == '.DS_Store':
        file_path = os.path.join(dirpath, file)
        try:
          os.remove(file_path)
          print(f"Removed: {file_path}")
        except Exception as e:
          print(f"Failed to remove {file_path}: {e}")


# Replace '/path/to/your/directory' with the path to the directory you want to clean up
remove_ds_store('./data')
