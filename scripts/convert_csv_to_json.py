import csv
import json


def convert_csv_to_json(csv_file_path, json_file_path):
  """
  Convert a CSV file to JSON format, combining duplicate column headers into arrays.

  Args:
      csv_file_path (str): Path to input CSV file
      json_file_path (str): Path to output JSON file
  """
  # First pass: identify duplicate columns and their indices
  duplicate_headers = {}
  header_indices = {}

  with open(csv_file_path, mode='r', encoding='utf-8') as csv_file:
    # Read the first row to get headers
    reader = csv.reader(csv_file)
    headers = next(reader)

    # Find duplicate headers and their positions
    for index, header in enumerate(headers):
      if header in header_indices:
        if header not in duplicate_headers:
          duplicate_headers[header] = [header_indices[header]]
        duplicate_headers[header].append(index)
      else:
        header_indices[header] = index

  # Second pass: read data and combine duplicate columns
  data = []
  with open(csv_file_path, mode='r', encoding='utf-8') as csv_file:
    reader = csv.reader(csv_file)
    headers = next(reader)  # Skip header row

    for row in reader:
      row_dict = {}

      # Process regular columns
      for header, index in header_indices.items():
        if header not in duplicate_headers:
          row_dict[header] = row[index] if index < len(row) else ""

      # Process duplicate columns
      for header, indices in duplicate_headers.items():
        # Get all non-empty values from duplicate columns
        values = [row[i] for i in indices if i < len(row) and row[i].strip()]
        if values:
          row_dict[header] = values
        else:
          row_dict[header] = []

      data.append(row_dict)

  # Write to JSON file
  with open(json_file_path, mode='w', encoding='utf-8') as json_file:
    json.dump(data, json_file, indent=2, ensure_ascii=False)


# Example usage
if __name__ == "__main__":
  # Replace these with your actual file paths
  input_csv = "../data/csv/Gin_Lane_Little_Plains Client_List.csv"
  output_json = "../scrap/output.json"

  try:
    convert_csv_to_json(input_csv, output_json)
    print(f"Successfully converted {input_csv} to {output_json}")
  except Exception as e:
    print(f"An error occurred: {str(e)}")
