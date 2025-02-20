import json
from datetime import datetime


def clean_value(value):
  """Clean and format the value for markdown."""
  if not value or value.strip() == "":
    return "Not available"
  return value.strip()


def generate_metadata_tags(json_data):
  """Generate metadata tags for better RAG performance."""
  tags = []

  # Add basic metadata
  tags.append("---")
  tags.append(f"title: {clean_value(json_data['Business Name'])} Case Study")
  tags.append(f"agency: {clean_value(json_data['Agency'])}")
  tags.append(f"client: {clean_value(json_data['Business Name'])}")
  tags.append(f"tier: {clean_value(json_data['Tier (1-3)'])}")
  tags.append(f"year: {clean_value(json_data['Years Worked With'])}")

  # Add service tags
  services = []
  if json_data.get('Did The Agency Do Strategy Work for the Client?') == 'Yes':
    services.append('strategy')
  if json_data.get('Did The Agency Do Brand Work for the Client?') == 'Yes':
    services.append('branding')
  if json_data.get('Did The Agency Creative Direct for the Client?') == 'Yes':
    services.append('creative-direction')
  if json_data.get('Did The Agency Do Experience Design for the Client?') == 'Yes':
    services.append('experience-design')
  if json_data.get('Did The Agency Create Content for the Client?') == 'Yes':
    services.append('content-creation')
  if json_data.get('Did The Agency Develop Technology for the Client?') == 'Yes':
    services.append('technology')

  tags.append(f"services: [{', '.join(services)}]")
  tags.append(f"lastUpdated: {datetime.now().strftime('%Y-%m-%d')}")
  tags.append("---\n")

  return "\n".join(tags)


def json_to_markdown(json_data):
  """
  Convert JSON object to markdown format optimized for RAG.
  Groups related information together for better context.
  """
  markdown = []

  # Add metadata tags
  markdown.append(generate_metadata_tags(json_data))

  # Company Overview
  markdown.append("# Company Overview\n")
  markdown.append(
    f"**Business Name:** {clean_value(json_data['Business Name'])}")
  markdown.append(
    f"**Description:** {clean_value(json_data['Can You Tell Me a One-Liner on the Client?'])}\n")

  # Agency Relationship
  markdown.append("## Agency Partnership\n")
  markdown.append(f"**Agency:** {clean_value(json_data['Agency'])}")
  markdown.append(
    f"**Partnership Summary:** {clean_value(json_data['Can You Tell Me a One-Liner of What the Agency Did for the Client?'])}")
  markdown.append(f"**Tier Level:** {clean_value(json_data['Tier (1-3)'])}")
  markdown.append(f"**Stage:** {clean_value(json_data['Stage Worked With'])}")
  markdown.append(
    f"**Years of Engagement:** {clean_value(json_data['Years Worked With'])}")
  markdown.append(
    f"**Equity Relationship:** {clean_value(json_data['Did the Agency Have Equity?'])}\n")

  # Exit Information
  has_exit_info = any(json_data.get(key, "").strip() for key in [
                      'Did the Startup Succesfully Exit?', 'If So, What Was the Exit Type?', 'What Year Was the Exit?'])
  if has_exit_info:
    markdown.append("## Exit Information\n")
    markdown.append(
      f"**Exit Status:** {clean_value(json_data['Did the Startup Succesfully Exit?'])}")
    markdown.append(
      f"**Exit Type:** {clean_value(json_data['If So, What Was the Exit Type?'])}")
    markdown.append(
      f"**Exit Year:** {clean_value(json_data['What Year Was the Exit?'])}\n")

  # Services Provided
  services_added = False

  # Strategy
  if json_data.get('Did The Agency Do Strategy Work for the Client?') == 'Yes':
    strategy_details = json_data.get('What Strategy Was Done? ', '').strip()
    if strategy_details:
      if not services_added:
        markdown.append("## Services Provided\n")
        services_added = True
      markdown.append("### Strategy")
      markdown.append(f"- {strategy_details}\n")

  # Branding
  if json_data.get('Did The Agency Do Brand Work for the Client?') == 'Yes':
    branding_details = json_data.get(
      'What Branding Work Was Done? ', '').strip()
    if branding_details:
      if not services_added:
        markdown.append("## Services Provided\n")
        services_added = True
      markdown.append("### Branding")
      markdown.append(f"- {branding_details}\n")

  # Creative Direction
  if json_data.get('Did The Agency Creative Direct for the Client?') == 'Yes':
    if not services_added:
      markdown.append("## Services Provided\n")
      services_added = True
    markdown.append("### Creative Direction")
    markdown.append("- Creative direction services provided\n")

  # Experience Design
  if json_data.get('Did The Agency Do Experience Design for the Client?') == 'Yes':
    experience_details = json_data.get(
      'What Type of Experience Design Was Done?', '').strip()
    if experience_details:
      if not services_added:
        markdown.append("## Services Provided\n")
        services_added = True
      markdown.append("### Experience Design")
      markdown.append(f"- {experience_details}\n")

  # Content Creation
  if json_data.get('Did The Agency Create Content for the Client?') == 'Yes':
    content_details = json_data.get(
      'What Type of Content Was Created?', '').strip()
    if content_details:
      if not services_added:
        markdown.append("## Services Provided\n")
        services_added = True
      markdown.append("### Content Creation")
      markdown.append(f"- {content_details}\n")

  # Technology Development
  if json_data.get('Did The Agency Develop Technology for the Client?') == 'Yes':
    tech_details = json_data.get(
      'What Type of Technology Was Created?', '').strip()
    if tech_details:
      if not services_added:
        markdown.append("## Services Provided\n")
        services_added = True
      markdown.append("### Technology Development")
      markdown.append(f"- {tech_details}\n")

  return "\n".join(markdown)


def convert_files(input_json_path, output_dir):
  """Convert JSON file containing multiple objects to separate markdown files."""
  try:
    with open(input_json_path, 'r', encoding='utf-8') as json_file:
      data = json.load(json_file)

    # Ensure output directory exists
    import os
    os.makedirs(output_dir, exist_ok=True)

    # Process each object in the array
    for idx, json_obj in enumerate(data):
      # Create filename using business name or index if name not available
      business_name = json_obj.get('Business Name', f'company_{idx}')
      filename = f"{business_name.lower().replace(' ', '_')}.md"
      output_path = os.path.join(output_dir, filename)

      # Convert to markdown and save
      markdown_content = json_to_markdown(json_obj)
      with open(output_path, 'w', encoding='utf-8') as md_file:
        md_file.write(markdown_content)

      print(f"Successfully created {output_path}")

  except Exception as e:
    print(f"An error occurred: {str(e)}")


# Example usage
if __name__ == "__main__":
  input_json = "../scrap/output.json"
  output_dir = "../scrap/case_studies"

  convert_files(input_json, output_dir)
