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


def generate_id():
  """Generate a short unique ID."""
  return str(uuid.uuid4())[:8]


def service_name_map(service):
  """Map service slugs to proper names."""
  mapping = {
      'strategy': 'Strategy',
      'branding': 'Branding and Positioning',
      'creative-direction': 'Creative Direction',
      'experience-design': 'Experience Design',
      'content-creation': 'Content Creation',
      'technology': 'Technology Development'
  }
  return mapping.get(service, service.replace('-', ' ').title())


def update_markdown_metadata(content, client_id):
  """Add client_id to markdown metadata."""
  if '---\n' not in content:
    return content

  metadata_end = content.find('---\n', content.find('---\n') + 4)
  if metadata_end == -1:
    return content

  # Insert client_id before the closing '---'
  metadata_section = content[:metadata_end]
  rest_of_content = content[metadata_end:]

  if 'client_id:' not in metadata_section:
    metadata_section = metadata_section.rstrip() + f'\nclient_id: {client_id}'

  return metadata_section + rest_of_content


def get_priority(tier):
  if tier == "Tier 1":
    return 0.7
  elif tier == "Tier 2":
    return 0.6
  elif tier == "Tier 3":
    return 0.5
  else:
    return 0.4


def process_files(markdown_dir, config_path):
  """Process markdown files and update project configuration."""
  try:
    # Load existing project config
    if os.path.exists(config_path):
      with open(config_path, 'r', encoding='utf-8') as f:
        project_config = json.load(f)
    else:
      project_config = []

    # Create a map of existing client_ids
    existing_configs = {config['document']: config for config in project_config}

    # Process each markdown file
    for filename in os.listdir(markdown_dir):
      if not filename.endswith('.md'):
        continue

      file_path = os.path.join(markdown_dir, filename)

      # Read markdown content
      with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

      # Parse metadata
      metadata = parse_markdown_metadata(content)

      #
      priority = get_priority(metadata.get('tier', '').strip())

      # Skip if already in config with client_id
      if filename in existing_configs and 'client_id' in existing_configs[filename]:
        print(f"Skipping {filename} - already configured")
        continue

      # Generate new client_id
      client_id = generate_id()
      project_id = generate_id()

      # Create new config entry
      new_config = {
          "document": filename,
          "priority": priority,
          "client_id": client_id,
          "project_id": project_id,
          "project_name": metadata.get('client', '').strip(),
          "content_type": "project",
          "services": [service_name_map(service) for service in metadata.get('services', [])],
          "technologies": []
      }

      # Update or add to project config
      if filename in existing_configs:
        for i, config in enumerate(project_config):
          if config['document'] == filename:
            project_config[i] = new_config
            break
      else:
        project_config.append(new_config)

      # Update markdown file with client_id
      updated_content = update_markdown_metadata(content, client_id)
      with open(file_path, 'w', encoding='utf-8') as f:
        f.write(updated_content)

      print(f"Processed {filename} - added client_id: {client_id}")

    # Write updated config
    with open(config_path, 'w', encoding='utf-8') as f:
      json.dump(project_config, f, indent=2)

    print(f"Successfully updated {config_path}")

  except Exception as e:
    print(f"An error occurred: {str(e)}")


# Example usage
if __name__ == "__main__":
  markdown_dir = "../data/projects/case_studies"
  config_path = "../data/project_config.json"

  process_files(markdown_dir, config_path)
