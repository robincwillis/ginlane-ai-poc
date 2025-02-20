import json
import re
import os


def extract_business_name(markdown_content):
  """Extract business name from markdown metadata."""
  match = re.search(r'client:\s*(.+)', markdown_content)
  if match:
    return match.group(1).strip()
  return None


def find_json_entry(json_data, business_name):
  """Find the corresponding JSON entry for a business name."""
  for entry in json_data:
    if entry.get('Business Name') == business_name:
      return entry
  return None


def format_service_section(service_key, values):
  """Format a service section with its values."""
  if not values:
    return ""

  # Convert single string to list if necessary
  if isinstance(values, str):
    values = [values]

  # Format the section
  lines = [f"**{service_key}**"]
  for value in values:
    if value.strip():
      lines.append(f"- {value.strip()}")
  return "\n".join(lines) + "\n"


def update_services_section(content, json_data):
  """Update the Services Provided section with new values from JSON."""
  # Service key mappings between markdown and JSON
  service_mappings = {
      'Strategy': 'What Strategy Was Done?',
      'Branding': 'What Branding Work Was Done?',
      'Creative Direction': 'Creative Direction',  # Special case
      'Experience Design': 'What Type of Experience Design Was Done?',
      'Content Creation': 'What Type of Content Was Created?',
      'Technology Development': 'What Type of Technology Was Created?'
  }

  # Find the Services Provided section
  sections = content.split('\n## ')
  updated_sections = []

  for section in sections:
    if not section.startswith('Services Provided'):
      updated_sections.append(section)
      continue

    # Start building new Services Provided section
    new_section = 'Services Provided\n\n'

    # Add each service that exists in the JSON data
    for md_service, json_key in service_mappings.items():
      if json_key == 'Creative Direction':
        # Special handling for Creative Direction
        if json_data.get('Did The Agency Creative Direct for the Client?') == 'Yes':
          new_section += format_service_section(
            md_service, 'Creative direction services provided')
      else:
        values = json_data.get(json_key, [])
        if values:  # Only add section if there are values
          new_section += format_service_section(md_service, values)

    updated_sections.append(new_section)

  return '\n## '.join(updated_sections)


def update_markdown_files(markdown_dir, json_file_path):
  """Process all markdown files and update their service sections."""
  try:
    # Load JSON data
    with open(json_file_path, 'r', encoding='utf-8') as f:
      json_data = json.load(f)

    # Process each markdown file
    for filename in os.listdir(markdown_dir):
      if not filename.endswith('.md'):
        continue

      file_path = os.path.join(markdown_dir, filename)

      # Read markdown content
      with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

      # Extract business name from markdown
      business_name = extract_business_name(content)
      if not business_name:
        print(f"Could not find business name in {filename}")
        continue

      # Find corresponding JSON entry
      json_entry = find_json_entry(json_data, business_name)
      if not json_entry:
        print(f"Could not find JSON data for {business_name}")
        continue

      # Update the content
      updated_content = update_services_section(content, json_entry)

      # Write updated content back to file
      with open(file_path, 'w', encoding='utf-8') as f:
        f.write(updated_content)

      print(f"Successfully updated services for {filename}")

  except Exception as e:
    print(f"An error occurred: {str(e)}")


# Example usage
if __name__ == "__main__":
  markdown_dir = "../data/projects/case_studies"
  json_file = "../scrap/output.json"

  update_markdown_files(markdown_dir, json_file)
