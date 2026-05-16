"""
File Grouper - Groups files by their base name (strips numbers)

Examples:
- akshay12345466.pdf → "akshay" folder
- akshay8765445.pdf → "akshay" folder
- invoice_001.pdf → "invoice" folder
- invoice_002.pdf → "invoice" folder
"""
import re
import os
from pathlib import Path
from typing import Dict, List
from collections import defaultdict


class FileGrouper:
    """Groups files by extracting base names (removing trailing numbers)"""
    
    def __init__(self):
        pass
    
    def extract_base_name(self, filename: str) -> str:
        """
        Extract the base name from a filename by removing trailing numbers and dates
        
        Examples:
            akshay12345466.pdf → akshay
            akshay8765445.pdf → akshay
            invoice_001.pdf → invoice
            Invoice_002.pdf → invoice
            report2024.pdf → report
            Screenshot 2026-01-20 at 8.26.24 PM.png → screenshot
            IMG_20240115_123456.jpg → img
            
        Args:
            filename: The filename (with or without extension)
            
        Returns:
            The base name with trailing numbers/dates removed
        """
        # Get filename without extension
        name = Path(filename).stem
        
        # Handle common patterns:
        
        # 1. Screenshots: "Screenshot 2026-01-20 at 8.26.24 PM" → "screenshot"
        if name.lower().startswith('screenshot'):
            return 'screenshots'
        
        # 2. IMG files: "IMG_20240115_123456" → "photos"
        if name.upper().startswith('IMG_') or name.upper().startswith('IMG-'):
            return 'photos'
        
        # 3. Remove date patterns like 2024-01-15, 2024_01_15, 20240115
        name = re.sub(r'\s*\d{4}[-_]?\d{2}[-_]?\d{2}.*$', '', name)
        
        # 4. Remove trailing numbers and underscores/dashes before them
        # Pattern: remove trailing _123, -123, or just 123
        base_name = re.sub(r'[-_\s]?\d+$', '', name)
        
        # If the entire name was numbers, use "numbers" as default
        if not base_name:
            base_name = "files"
        
        # Clean up any trailing underscores, dashes, or spaces
        base_name = base_name.rstrip('-_ ')
        
        result = base_name.lower()

        # Strip trailing "inc" — ignore company suffix for grouping.
        if result.endswith('inc') and len(result) > 3:
            result = result[:-3]

        return result

    
    def group_files(self, file_paths: List[str]) -> Dict[str, List[str]]:
        """
        Group files by their base names
        
        Args:
            file_paths: List of file paths
            
        Returns:
            Dictionary with base names as keys and list of file paths as values
        """
        groups = defaultdict(list)
        
        for path in file_paths:
            filename = os.path.basename(path)
            base_name = self.extract_base_name(filename)
            groups[base_name].append(path)
        
        # Sort files within each group alphabetically
        for base_name in groups:
            groups[base_name].sort(key=lambda x: os.path.basename(x).lower())
        
        return dict(groups)
    
    def display_groups(self, groups: Dict[str, List[str]]) -> None:
        """Pretty print the file groups"""
        print(f"\n📁 File Groups ({len(groups)} groups):")
        print("-" * 50)
        
        for base_name, files in sorted(groups.items()):
            print(f"\n  📂 {base_name}/ ({len(files)} files)")
            for f in files:
                print(f"      └── {os.path.basename(f)}")
    
    def get_group_summary(self, groups: Dict[str, List[str]]) -> str:
        """Get a summary of the groups"""
        total_files = sum(len(files) for files in groups.values())
        return f"{len(groups)} folders, {total_files} files"


# Quick test
if __name__ == "__main__":
    grouper = FileGrouper()
    
    # Test extraction
    test_files = [
        "akshay12345466.pdf",
        "akshay8765445.pdf",
        "invoice_001.pdf",
        "invoice_002.pdf",
        "report2024.pdf",
        "photo.jpg",
    ]
    
    print("Base name extraction:")
    for f in test_files:
        print(f"  {f} → {grouper.extract_base_name(f)}")
    
    # Test grouping
    groups = grouper.group_files(test_files)
    grouper.display_groups(groups)
