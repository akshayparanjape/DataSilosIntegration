import os
import sys
import json
import argparse
import datetime
import pandas as pd
import google.generativeai as genai
from dotenv import load_dotenv
from presidio_analyzer import AnalyzerEngine
import signal
import time

# Load environment
load_dotenv()

# Exit gracefully on Ctrl+C
def signal_handler(sig, frame):
    print("\n👋 Goodbye!")
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)

# Configure Gemini with environment variable check
api_key = os.getenv("GOOGLE_API_KEY")
if not api_key:
    print("❌ Error: GOOGLE_API_KEY environment variable not found.")
    print("Please set it in your .env file or environment.")
    sys.exit(1)

genai.configure(api_key=api_key)

# Initialize analyzer only once for performance
analyzer = AnalyzerEngine()
MAX_RETRIES = 3


def log_to_file(prompt, response, suffix="log"):
    """Log interactions for debugging purposes"""
    try:
        os.makedirs("logs", exist_ok=True)
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"logs/{timestamp}_{suffix}.txt"
        with open(filename, "w", encoding='utf-8') as f:
            f.write("Prompt:\n" + prompt + "\n\nResponse:\n" + response)
    except Exception as e:
        print(f"⚠️ Warning: Could not write log file: {e}")


def scrub_pii(df):
    """Remove PII from dataframe - optimized version"""
    def scrub_cell(val):
        if pd.isna(val) or not isinstance(val, str) or len(val) < 3:  # Skip NaN, non-strings, and very short strings
            return val
        try:
            results = analyzer.analyze(text=str(val), entities=None, language='en')
            # Sort by start position in reverse to avoid index shifting
            for r in sorted(results, key=lambda x: x.start, reverse=True):
                val = val[:r.start] + "<PII>" + val[r.end:]
        except Exception:
            pass  # If PII detection fails, return original value
        return val

    # Use map instead of deprecated applymap, only on string columns for performance
    try:
        df_copy = df.copy()
        string_columns = df_copy.select_dtypes(include=['object', 'string']).columns.tolist()

        for col in string_columns:
            if col in df_copy.columns:  # Ensure column exists
                df_copy[col] = df_copy[col].astype(str).map(scrub_cell)

        return df_copy
    except Exception as e:
        print(f"⚠️ Warning: PII scrubbing failed ({e}), returning original data")
        return df.copy()


def sample_dataframe(df, max_rows=3, max_cols=8):
    """Create a smaller sample for faster processing"""
    sampled = df.iloc[:max_rows, :max_cols]
    return sampled


def generate_etl_code(user_prompt, datasets, return_both=False):
    """Generate ETL code using Gemini with improved prompt"""

    # Create lightweight dataset preview for performance
    dataset_info = []
    for name, df in datasets.items():
        try:
            # Get basic info without PII scrubbing for performance
            info = f"{name}:\n"
            info += f"Shape: {df.shape}\n"
            info += f"Columns: {list(df.columns[:10])}{'...' if len(df.columns) > 10 else ''}\n"
            info += f"Data types: {df.dtypes.value_counts().to_dict()}\n"

            # Show a small sample without PII scrubbing for speed
            sample = df.head(2)
            info += f"Sample data (first 2 rows):\n{sample.to_string(index=False, max_cols=5)}\n"
            dataset_info.append(info)
        except Exception as e:
            dataset_info.append(f"{name}: Error reading dataset - {e}\n")

    dataset_preview = "\n".join(dataset_info)

    prompt = f"""
You are an expert data engineer focused on delivering exactly what the user needs.

DATASETS AVAILABLE:
{dataset_preview}

USER REQUEST: "{user_prompt}"

Your primary goal is to fulfill the user's specific request. Be practical and user-focused.

Respond ONLY in this JSON format:
{{
    "explanation": "<brief explanation of your approach, focusing on the user's goals>",
    "code": "<efficient Python pandas code that directly addresses the user's request>"
}}

CRITICAL REQUIREMENTS:
- Use variables from `datasets` dictionary (e.g., `datasets["secom_data.csv"]`)
- generate a string starting with the current timestamp followed by a random 4 digit string and append it to the final result's filename as directed below.
- Save final result to './output/cleaned_output_<timestamp_random_number>.csv'
- Handle missing values appropriately (use pd.isna() checks)
- Use proper pandas syntax (df.columns not df.columns())
- Import any required libraries at the top (from sklearn.decomposition import PCA, from sklearn.preprocessing import StandardScaler, etc.)
- Write efficient, clean code with proper error handling
- No print statements
- Focus on the user's specific needs and preferences

COMMON PATTERNS FOR THIS DATA:
- For PCA: StandardScaler + PCA from sklearn
- For anomaly detection: Usually combine features with labels
- For cleaning: Handle NaN values, convert to numeric where needed
""".strip()

    try:
        model = genai.GenerativeModel("gemini-2.5-flash")
        response = model.generate_content(prompt)
        raw_text = response.text.strip()

        # Clean up markdown formatting
        if raw_text.startswith("```json"):
            raw_text = raw_text[7:]
        if raw_text.endswith("```"):
            raw_text = raw_text[:-3]
        raw_text = raw_text.strip()

        log_to_file(prompt, raw_text, "gemini_code")

        response_json = json.loads(raw_text)
        explanation = response_json.get("explanation", "No explanation provided")
        code = response_json.get("code", "")

        if not code.strip():
            return ("# No code generated", "Failed to generate code") if return_both else "# No code generated"

    except json.JSONDecodeError as e:
        explanation = f"⚠️ Failed to parse Gemini response as JSON: {e}"
        code = f"# Error: Could not parse response\n# Raw response: {raw_text}"
    except Exception as e:
        explanation = f"⚠️ Error generating code: {e}"
        code = "# Error occurred during code generation"

    return (code, explanation) if return_both else code


def execute_etl_code(code, datasets):
    """Execute generated ETL code with error handling"""
    os.makedirs("output", exist_ok=True)

    # Prepare execution environment with common imports
    env = {
        "pd": pd,
        "datasets": datasets,
        "os": os,
        "numpy": __import__("numpy"),
        "__builtins__": __builtins__
    }

    # Add common sklearn imports that might be needed
    try:
        from sklearn.decomposition import PCA
        from sklearn.preprocessing import StandardScaler
        env["PCA"] = PCA
        env["StandardScaler"] = StandardScaler
    except ImportError:
        pass

    print("🔄 Executing ETL code...")

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            exec(code, env)
            break
        except Exception as e:
            error_msg = f"❌ Attempt {attempt}/{MAX_RETRIES} failed: {str(e)}"
            print(error_msg)

            if attempt == MAX_RETRIES:
                # Show the actual code that failed for debugging
                print("📝 Failed code:")
                print("-" * 40)
                print(code)
                print("-" * 40)
                return f"❌ Failed after {MAX_RETRIES} attempts. Last error: {e}"

            time.sleep(1)  # Brief pause between retries

    output_path = "./output/cleaned_output.csv"

    if not os.path.exists(output_path):
        return "⚠️ No output CSV was generated. Check if the code saves to './output/cleaned_output.csv'"

    try:
        df_clean = pd.read_csv(output_path)
        if df_clean.empty:
            return "⚠️ Warning: Generated CSV file is empty."

        row_count = len(df_clean)
        col_count = len(df_clean.columns)
        return f"✅ ETL completed successfully!\n📊 Output: {row_count} rows, {col_count} columns\n💾 Saved to: {output_path}"

    except Exception as e:
        return f"⚠️ Output file created but validation failed: {e}"


def load_datasets(file_paths):
    """Load datasets with error handling"""
    datasets = {}

    for path in file_paths:
        try:
            if not os.path.exists(path):
                print(f"❌ File not found: {path}")
                continue

            name = os.path.basename(path)
            print(f"📂 Loading {name}...")

            df = pd.read_csv(path)
            datasets[name] = df
            print(f"✅ Loaded {name}: {df.shape[0]} rows, {df.shape[1]} columns")

        except Exception as e:
            print(f"❌ Error loading {path}: {e}")

    return datasets


def main():
    print("🤖 ETL Agent - AI-Powered Data Processing")
    print("=" * 50)

    parser = argparse.ArgumentParser(
        description="AI-powered ETL agent for CSV data processing",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python auto_etl.py --source data.csv --output ./results
  python auto_etl.py --source file1.csv file2.csv --output ./cleaned_data

Environment Variables:
  GOOGLE_API_KEY: Required Google Gemini API key
        """
    )

    parser.add_argument(
        "--source",
        nargs='+',
        required=True,
        help="Paths to one or more CSV files to process"
    )

    parser.add_argument(
        "--output_dir",
        default="./output",
        help="Directory to save processed output (default: ./output)"
    )

    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose logging"
    )

    args = parser.parse_args()

    # Load datasets
    datasets = load_datasets(args.source)

    if not datasets:
        print("❌ No datasets could be loaded. Exiting.")
        sys.exit(1)

    print(f"\n📋 Loaded {len(datasets)} dataset(s)")
    print("💡 Tip: Be specific about what you want to do with your data!")
    print("🚪 Type 'quit', 'exit', or 'q' to exit\n")

    while True:
        try:
            query = input("🧠 What would you like to do with your data? ").strip()

            if query.lower() in ['q', 'quit', 'exit']:
                print("👋 Goodbye!")
                break

            if not query:
                print("Please enter a request or 'q' to quit.")
                continue

            print("\n🔄 Generating solution...")

            code, explanation = generate_etl_code(query, datasets, return_both=True)

            # Check if actual code was generated
            if code.strip().startswith("#") and "Error" in code:
                print(f"\n❌ {explanation}")
                continue

            print(f"\n🔍 Plan: {explanation}")

            # Only ask for confirmation if we have valid generated code
            if code.strip() and not code.strip().startswith("# Error"):
                if args.verbose:
                    print(f"\n📝 Generated code:\n{code}\n")

                confirm = input("▶️ Execute this plan? (y/n): ").strip().lower()
                if confirm in ['y', 'yes']:
                    result = execute_etl_code(code, datasets)
                    print(f"\n{result}\n")
                else:
                    print("⏭️ Skipped execution.\n")
            else:
                print("❌ No valid code was generated. Please try rephrasing your request.\n")

        except KeyboardInterrupt:
            print("\n👋 Goodbye!")
            break
        except Exception as e:
            print(f"❌ Unexpected error: {e}")


if __name__ == "__main__":
    main()
