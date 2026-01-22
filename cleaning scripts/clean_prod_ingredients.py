#!/usr/bin/env python3
"""
Clean Product Ingredients CSV
Removes messy data, handles multi-line fields, and creates a clean CSV with exactly:
- product_name
- active_ingredient_id
- active_ingredient_name
- strength

Usage:
    python clean_product_ingredients.py
"""

import pandas as pd
import os
from pathlib import Path

def clean_product_ingredients(input_file, output_file):
    """
    Clean the product_ingredients CSV file.
    
    Handles:
    - Multi-line text fields
    - Duplicate rows
    - Missing/null values
    - Extra whitespace
    """
    print("=" * 70)
    print("Cleaning Product Ingredients CSV")
    print("=" * 70)
    
    # Read the CSV with proper handling of multi-line fields
    print(f"\n📂 Reading: {input_file}")
    try:
        df = pd.read_csv(input_file, encoding='utf-8', on_bad_lines='skip')
        print(f"   ✓ Loaded {len(df):,} rows")
    except Exception as e:
        print(f"   ✗ Error reading file: {e}")
        return
    
    print(f"\n🔍 Original data:")
    print(f"   Columns: {list(df.columns)}")
    print(f"   Total rows: {len(df):,}")
    
    # Step 1: Select only the required columns
    required_columns = ['product_name', 'active_ingredient_id', 'active_ingredient_name', 'strength']
    
    # Check if columns exist
    missing_cols = [col for col in required_columns if col not in df.columns]
    if missing_cols:
        print(f"\n   ⚠️  Missing columns: {missing_cols}")
        print(f"   Available columns: {list(df.columns)}")
        return
    
    df_clean = df[required_columns].copy()
    print(f"\n✂️  Keeping only required columns: {required_columns}")
    
    # Step 2: Remove rows with null product_name or active_ingredient_id (critical fields)
    before_null = len(df_clean)
    df_clean = df_clean.dropna(subset=['product_name', 'active_ingredient_id'])
    removed_null = before_null - len(df_clean)
    if removed_null > 0:
        print(f"   ✓ Removed {removed_null:,} rows with missing product_name or active_ingredient_id")
    
    # Step 3: Strip whitespace from string columns
    print(f"\n🧹 Cleaning whitespace...")
    df_clean['product_name'] = df_clean['product_name'].astype(str).str.strip()
    df_clean['active_ingredient_id'] = df_clean['active_ingredient_id'].astype(str).str.strip()
    df_clean['active_ingredient_name'] = df_clean['active_ingredient_name'].astype(str).str.strip()
    df_clean['strength'] = df_clean['strength'].astype(str).str.strip()
    
    # Replace 'nan' string with empty string for strength
    df_clean['strength'] = df_clean['strength'].replace('nan', '')
    
    # Step 4: Remove exact duplicates
    before_dup = len(df_clean)
    df_clean = df_clean.drop_duplicates()
    removed_dup = before_dup - len(df_clean)
    if removed_dup > 0:
        print(f"   ✓ Removed {removed_dup:,} exact duplicate rows")
    
    # Step 5: Remove duplicates based on product_name + active_ingredient_id
    # Keep the first occurrence
    before_key_dup = len(df_clean)
    df_clean = df_clean.drop_duplicates(subset=['product_name', 'active_ingredient_id'], keep='first')
    removed_key_dup = before_key_dup - len(df_clean)
    if removed_key_dup > 0:
        print(f"   ✓ Removed {removed_key_dup:,} duplicate product-ingredient pairs")
    
    # Step 6: Remove any rows where product_name or active_ingredient_id are empty strings
    before_empty = len(df_clean)
    df_clean = df_clean[
        (df_clean['product_name'] != '') & 
        (df_clean['active_ingredient_id'] != '')
    ]
    removed_empty = before_empty - len(df_clean)
    if removed_empty > 0:
        print(f"   ✓ Removed {removed_empty:,} rows with empty product_name or active_ingredient_id")
    
    # Step 7: Validate active_ingredient_id format (should start with DB)
    invalid_ids = df_clean[~df_clean['active_ingredient_id'].str.startswith('DB')]
    if len(invalid_ids) > 0:
        print(f"\n   ⚠️  Warning: Found {len(invalid_ids):,} rows with invalid DrugBank IDs")
        print(f"   Example invalid IDs:")
        for idx, row in invalid_ids.head(5).iterrows():
            print(f"      {row['active_ingredient_id']} (product: {row['product_name'][:50]})")
        
        # Option to remove them
        print(f"\n   Keeping them for now, but they may cause issues...")
    
    # Step 8: Final statistics
    print(f"\n📊 Cleaned data summary:")
    print(f"   Final rows: {len(df_clean):,}")
    print(f"   Unique products: {df_clean['product_name'].nunique():,}")
    print(f"   Unique active ingredients: {df_clean['active_ingredient_id'].nunique():,}")
    print(f"   Rows with strength data: {(df_clean['strength'] != '').sum():,}")
    print(f"   Rows without strength: {(df_clean['strength'] == '').sum():,}")
    
    # Show examples
    print(f"\n📋 Sample cleaned data (first 5 rows):")
    print(df_clean.head(5).to_string(index=False))
    
    # Step 9: Save cleaned data
    print(f"\n💾 Saving cleaned data to: {output_file}")
    df_clean.to_csv(output_file, index=False, encoding='utf-8')
    print(f"   ✓ Saved {len(df_clean):,} rows")
    
    # Step 10: Summary
    print(f"\n" + "=" * 70)
    print(f"✅ Cleaning Complete!")
    print(f"=" * 70)
    print(f"Original rows:  {len(df):,}")
    print(f"Cleaned rows:   {len(df_clean):,}")
    print(f"Rows removed:   {len(df) - len(df_clean):,}")
    print(f"\nCleaned file:   {output_file}")
    print(f"Original file:  {input_file} (unchanged)")
    print(f"\n💡 Next step: Use the cleaned file for Neo4j import")

def main():
    # Set up paths
    data_dir = os.getenv("DRUGBANK_DATA_DIR", "drugbank_data")
    input_file = os.path.join(data_dir, "product_ingredients.csv")
    output_file = os.path.join(data_dir, "product_ingredients_clean.csv")
    
    # Check if input file exists
    if not os.path.exists(input_file):
        print(f"❌ Error: Input file not found: {input_file}")
        print(f"\nPlease ensure the file exists in the drugbank_data/ directory")
        return
    
    # Clean the data
    clean_product_ingredients(input_file, output_file)
    
    # Verify the cleaned file
    print(f"\n🔍 Verifying cleaned file...")
    try:
        df_verify = pd.read_csv(output_file)
        print(f"   ✓ Cleaned file is readable")
        print(f"   ✓ Contains {len(df_verify):,} rows")
        print(f"   ✓ Columns: {list(df_verify.columns)}")
        
        # Check for any remaining issues
        null_counts = df_verify.isnull().sum()
        if null_counts.sum() > 0:
            print(f"\n   ⚠️  Null value counts:")
            for col, count in null_counts.items():
                if count > 0:
                    print(f"      {col}: {count:,}")
        else:
            print(f"   ✓ No null values")
        
    except Exception as e:
        print(f"   ✗ Error verifying file: {e}")

if __name__ == "__main__":
    main()