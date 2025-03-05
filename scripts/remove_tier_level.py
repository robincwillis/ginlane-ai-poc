import os
import re

def remove_tier_level_line(directory_path, backup=False):
    """
    Scans a directory for markdown files and removes lines containing "**Tier Level:**"
    from each file.
    
    Args:
        directory_path (str): Path to the directory containing markdown files
        backup (bool): Whether to create backup files before modifying
        
    Returns:
        dict: Statistics about the operation
    """
    stats = {
        "total_files_processed": 0,
        "files_modified": 0,
        "lines_removed": 0,
        "errors": 0
    }
    
    # Pattern to match "**Tier Level:**" lines with various formats
    pattern = re.compile(r'^\s*\*\*Tier Level:\*\*.*$', re.MULTILINE)
    
    # Get all markdown files in the directory
    for filename in os.listdir(directory_path):
        if not filename.endswith(('.md', '.markdown')):
            continue
        
        file_path = os.path.join(directory_path, filename)
        stats["total_files_processed"] += 1
        
        try:
            # Read the file
            with open(file_path, 'r', encoding='utf-8') as file:
                content = file.read()
            
            # Count occurrences of the pattern
            matches = pattern.findall(content)
            if not matches:
                # No matches, skip to next file
                continue
            
            # Create backup if requested
            if backup:
                backup_path = file_path + '.bak'
                with open(backup_path, 'w', encoding='utf-8') as backup_file:
                    backup_file.write(content)
            
            # Remove the matching lines
            modified_content = pattern.sub('', content)
            
            # Write the modified content back to the file
            with open(file_path, 'w', encoding='utf-8') as file:
                file.write(modified_content)
            
            # Update stats
            stats["files_modified"] += 1
            stats["lines_removed"] += len(matches)
            
        except Exception as e:
            print(f"Error processing {filename}: {str(e)}")
            stats["errors"] += 1
    
    return stats

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Remove "**Tier Level:**" lines from markdown files.')
    parser.add_argument('directory', help='Directory containing markdown files')
    parser.add_argument('--no-backup', action='store_false', dest='backup', 
                        help='Do not create backup files')
    
    args = parser.parse_args()
    
    if not os.path.isdir(args.directory):
        print(f"Error: {args.directory} is not a valid directory.")
        exit(1)
    
    print(f"Processing markdown files in {args.directory}...")
    stats = remove_tier_level_line(args.directory, backup=args.backup)
    
    print("\nOperation complete:")
    print(f"Total files processed: {stats['total_files_processed']}")
    print(f"Files modified: {stats['files_modified']}")
    print(f"Lines removed: {stats['lines_removed']}")
    
    if stats["errors"] > 0:
        print(f"Errors encountered: {stats['errors']}")
        
    if args.backup and stats["files_modified"] > 0:
        print(f"\nBackup files were created with .bak extension.")