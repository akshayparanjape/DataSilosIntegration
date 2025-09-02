import pandas as pd
import argparse

# Set up command-line argument parsing
parser = argparse.ArgumentParser(description="View a .parquet file")
parser.add_argument("file", help="Path to the parquet file")
parser.add_argument("--rows", type=int, default=5, help="Number of rows to display (default: 5)")
args = parser.parse_args()

# Read the parquet file
df = pd.read_parquet(args.file)
df.to_csv("DF")
#pd.save("file", df)
# Display the first few rows
print(df.head(args.rows))

# Optional: show basic info
print("\n--- File Info ---")
print(df.info())
