import os
import json
import re
import uuid


def parse_markdown_metadata(content):
  """Extract metadata from markdown file."""
  metadata = {}
  metadata_match = re.match(r'^---\n(.*?)\n---', content, re.DOTALL)
  if metadata_match:
    metadata_text = metadata_match.group(1)
    for line in metadata_text.split('\n'):
      if ':' in line:
        key, value = line.split(':', 1)
        key = key.strip()
        value = value.strip()
        if key == 'services':
          # Convert string "[strategy, branding]" to list
          value = value.strip('[]').replace(' ', '').split(',')
        metadata[key] = value
  return metadata


def get_project_ids(project_config, client_id):
  """Get all project ids for client_id"""
  project_ids = [project['project_id']
                 for project in project_config if project['client_id'] == client_id]
  return project_ids


def parse_categories(content):
  """Get Categories from Markdown file"""
  match = re.search(r'Category:\s*(.+)', content)
  if match:
    categories = match.group(1).split(', ')
    # Strip '**' from the beginning of the first category if present
    categories = [category.strip('** ') for category in categories]
    return categories
  return []


def process_files(markdown_dir, project_config_path, client_config_path):
  """Process markdown files and update client configuration."""
  try:
    if os.path.exists(project_config_path):
      with open(project_config_path, 'r', encoding='utf-8') as f:
        project_config = json.load(f)
    else:
      project_config = []

    if os.path.exists(client_config_path):
      with open(client_config_path, 'r', encoding='utf-8') as f:
        client_config = json.load(f)
    else:
      client_config = []

    # Create a map of existing client_ids
    existing_client_ids = {config['client_id']: config for config in client_config}
    print("Existing client IDs:", existing_client_ids)

    # Process each markdown file
    for filename in os.listdir(markdown_dir):
      if not filename.endswith('.md'):
        continue

      file_path = os.path.join(markdown_dir, filename)

      # Read markdown content
      with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

      categories = parse_categories(content)
      metadata = parse_markdown_metadata(content)

      client_id = metadata.get('client_id')
      project_ids = get_project_ids(project_config, client_id)

      if client_id is None:
        print(f"Skipping {filename} - no client_id")
        continue

      # If not in config
      if client_id in existing_client_ids:
        print(f"Skipping {filename} - already configured")
        continue

      new_config = {
        "client_id": client_id,
        "client_name": metadata.get('client', '').strip(),
        "categories": categories,
        "project_ids": project_ids
      }

      client_config.append(new_config)
      print(f"Processed {filename} - added client_id: {client_id}")

      print(new_config)
    with open(client_config_path, 'w', encoding='utf-8') as f:
      json.dump(client_config, f, indent=2)

  except Exception as e:
    print(f"An error occurred: {str(e)}")

  # Example usage
if __name__ == "__main__":
  markdown_dir = "../data/projects/"
  project_config_path = "../data/project_config.json"
  client_config_path = "../data/client_config.json"

  process_files(markdown_dir, project_config_path, client_config_path)
