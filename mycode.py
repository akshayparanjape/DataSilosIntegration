"""
Agent: Schema + Cleaning (LangChain) with Python REPL
File: enhanced_agent_with_repl.py

Purpose: An enhanced conversational ETL agent that:
 - Uses LangChain's PythonAstREPLTool for dynamic code execution
 - Allows arbitrary pandas operations through natural language instructions
 - Maintains conversational state with the DataFrame in REPL context
 - Provides full flexibility for data transformations and analysis

Dependencies:
  pip install langchain langchain-experimental pandas pyarrow presidio-analyzer presidio-anonymizer python-dotenv google-generativeai spacy scikit-learn
  python -m spacy download en_core_web_lg
"""

from __future__ import annotations
import json
import os
import re
import hashlib
import logging
import textwrap
from typing import Dict, List, Any, Tuple, Optional
import time
import pandas as pd
from dotenv import load_dotenv

# Presidio
from presidio_analyzer import AnalyzerEngine, RecognizerResult
from presidio_anonymizer import AnonymizerEngine

# LangChain imports
from langchain.schema import SystemMessage, HumanMessage, AIMessage
from langchain_experimental.tools.python.tool import PythonAstREPLTool

# Google Gemini client
import google.generativeai as genai

# ---------------- Env & Logging ----------------

# load .env file automatically
load_dotenv()

LOG_DIR = os.environ.get("ETL_LOG_DIR", "./logs/agents")
os.makedirs(LOG_DIR, exist_ok=True)

logging.basicConfig(
    filename=os.path.join(LOG_DIR, "enhanced_agent_run.log"),
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
logger = logging.getLogger("enhanced_agent")

ROWS_PER_PROMPT = int(os.environ.get("ROWS_PER_PROMPT", 8))
MAX_PROMPT_CHARS = int(os.environ.get("MAX_PROMPT_CHARS", 12_000))

# ---------------- Utils ----------------
def hash_value(v: str) -> str:
    return hashlib.sha256(v.encode("utf-8")).hexdigest()[:12]

# ---------------- PII Scrubber ----------------
class PIIScrubber:
    def __init__(self):
        self.analyzer = AnalyzerEngine()
        self.anonymizer = AnonymizerEngine()

    def _scrub_cell(self, text: str) -> Tuple[str, Dict[str, str]]:
        if not isinstance(text, str) or not text.strip():
            return text, {}
        results: List[RecognizerResult] = self.analyzer.analyze(text=text, language="en")
        if not results:
            return text, {}
        redact_map = {}
        anonymized = text
        for r in sorted(results, key=lambda x: x.start):
            span = text[r.start:r.end]
            token = f"{r.entity_type.upper()}_{hash_value(span)}"
            redact_map[span] = token
            anonymized = anonymized.replace(span, token)
        return anonymized, redact_map

    def scrub_dataframe(self, df: pd.DataFrame, text_cols: Optional[List[str]] = None) -> Tuple[pd.DataFrame, Dict[str, Dict[str, str]]]:
        df_copy = df.copy()
        redact_summary: Dict[str, Dict[str, str]] = {}
        if text_cols is None:
            text_cols = df_copy.select_dtypes(include=[object]).columns.tolist()
        for col in text_cols:
            col_map: Dict[str, str] = {}
            def _apply(cell):
                try:
                    anonymized, cmap = self._scrub_cell(cell)
                    col_map.update(cmap)
                    return anonymized
                except Exception as e:
                    logger.exception("Error scrubbing cell: %s", e)
                    return cell
            df_copy[col] = df_copy[col].apply(_apply)
            if col_map:
                redact_summary[col] = col_map
        return df_copy, redact_summary

# ---------------- Enhanced Python REPL Executor ----------------
class PythonREPLExecutor:
    """
    Enhanced executor using LangChain's PythonAstREPLTool for dynamic code execution.
    Maintains DataFrame state in REPL context for conversational operations.
    """

    def __init__(self, df: pd.DataFrame):
        # Initialize Python REPL tool with DataFrame in locals
        self.repl_tool = PythonAstREPLTool(
            locals={
                "df": df.copy(),
                "pd": pd,
                "np": None,  # Will import numpy if needed
            }
        )
        # Try to import commonly used libraries into REPL context
        self._setup_repl_environment()

    def _setup_repl_environment(self):
        """Setup common data science libraries in REPL environment"""
        setup_code = """
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import re
import json

# Make sure df is available
print(f"DataFrame loaded with shape: {df.shape}")
print(f"Columns: {list(df.columns)}")
        """
        try:
            result = self.repl_tool.run(setup_code)
            logger.info("REPL environment setup completed: %s", result)
        except Exception as e:
            logger.warning("REPL setup had issues: %s", e)

    def execute_code(self, code: str) -> Tuple[bool, str, pd.DataFrame]:
        """
        Execute Python code in REPL context.
        Returns: (success, output_message, updated_dataframe)
        """
        try:
            # Execute the code
            output = self.repl_tool.run(code)

            # Get updated DataFrame from REPL locals
            updated_df = self.repl_tool.locals.get("df")

            success = True
            message = f"Code executed successfully.\nOutput: {output}" if output else "Code executed successfully."

            return success, message, updated_df

        except Exception as e:
            error_msg = f"Error executing code: {str(e)}"
            logger.error(error_msg)
            # Return original DataFrame on error
            original_df = self.repl_tool.locals.get("df")
            return False, error_msg, original_df

    def get_current_dataframe(self) -> pd.DataFrame:
        """Get current state of DataFrame from REPL"""
        return self.repl_tool.locals.get("df").copy()

    def update_dataframe(self, new_df: pd.DataFrame):
        """Update DataFrame in REPL context"""
        self.repl_tool.locals["df"] = new_df.copy()

# ---------------- Gemini LLM Adapter ----------------
class LocalLLMAdapter:
    def __init__(self, model_name="gemini-2.0-flash"):
        api_key = os.environ.get("GOOGLE_API_KEY")
        if not api_key:
            raise RuntimeError("GOOGLE_API_KEY not set. Put it in your .env file!")
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel(model_name)

    def call(self, prompt: str, max_tokens: int = 2048) -> Dict[str, Any]:
        response = self.model.generate_content(
            prompt,
            generation_config={"max_output_tokens": max_tokens}
        )
        return {"content": response.text, "tokens": len(prompt.split())}

# ---------------- Enhanced Conversational ETL Agent ----------------
class EnhancedConversationalETLAgent:
    """
    Enhanced conversational agent with Python REPL for unlimited flexibility.
    Allows freeform natural language interaction for any data processing task.
    """

    def __init__(self, sample_path: str, out_dir: str):
        self.sample_path = sample_path
        self.out_dir = out_dir
        self.llm = LocalLLMAdapter()
        self.scrubber = PIIScrubber()

        # Load original data
        self.df_original = pd.read_csv(sample_path)

        # Initialize Python REPL executor with DataFrame
        self.repl_executor = PythonREPLExecutor(self.df_original)

        # Track execution history
        self.execution_history = []

        print(f"📊 Loaded file: {self.sample_path}")
        print(f"   Rows: {self.df_original.shape[0]}, Columns: {self.df_original.shape[1]}")
        print(f"   Columns: {list(self.df_original.columns)}")
        print("\n🔍 Preview of data (first 5 rows):")
        print(self.df_original.head(5).to_string(index=False))
        print("\n" + "="*60)

    def build_llm_prompt(self, user_instruction: str) -> str:
        """Build prompt for LLM to generate Python code based on user instruction"""

        # Get current DataFrame state
        current_df = self.repl_executor.get_current_dataframe()
        sample_csv = current_df.head(5).to_csv(index=False)

        # Include basic DataFrame info
        df_info = f"""
DataFrame Info:
- Shape: {current_df.shape}
- Columns: {list(current_df.columns)}
- Data types: {dict(current_df.dtypes)}
- Null values: {dict(current_df.isnull().sum())}
        """

        prompt = f"""
You are an expert Python data analyst. You have access to a pandas DataFrame named 'df'.

Current DataFrame preview (first 5 rows):
{sample_csv}

{df_info}

User instruction:
"{user_instruction}"

Please write Python code to accomplish what the user requested. The DataFrame is available as 'df'.

IMPORTANT INSTRUCTIONS:
1. Write ONLY executable Python code
2. Assume pandas is imported as 'pd' and numpy as 'np'
3. The DataFrame variable is named 'df'
4. Enclose your code in triple backticks (```)
5. Do NOT include any explanatory text outside the code block
6. Make sure your code modifies 'df' in-place or reassigns it if needed
7. You can use print() statements to show results or progress
8. For file operations, save to the current directory
9. package sklearn is deprecated and always use scikit-learn instead.
Example format:
```python
# Your Python code here
df = df.dropna()
print(f"DataFrame shape after dropping nulls: {{df.shape}}")
```

Now write the Python code for the user's request:
        """
        return prompt

    def extract_code_from_response(self, llm_response: str) -> Optional[str]:
        """Extract Python code from LLM response"""
        # Look for code blocks with python or without language specifier
        patterns = [
            r"```python\n(.*?)\n```",
            r"```\n(.*?)\n```",
            r"```python(.*?)```",
            r"```(.*?)```"
        ]

        for pattern in patterns:
            match = re.search(pattern, llm_response, re.DOTALL)
            if match:
                return match.group(1).strip()

        return None

    def process_user_instruction(self, user_instruction: str) -> Tuple[bool, str]:
        """
        Process a natural language instruction from user.
        Returns: (success, response_message)
        """
        try:
            # Generate prompt and get LLM response
            prompt = self.build_llm_prompt(user_instruction)
            logger.info("Generated prompt for instruction: %s", user_instruction[:100])

            llm_response = self.llm.call(prompt)
            response_content = llm_response.get("content", "").strip()

            # Log the LLM response
            logger.info("LLM response: %s", response_content[:200])

            # Extract code from response
            code = self.extract_code_from_response(response_content)

            if not code:
                return False, "❌ Could not extract executable code from LLM response."

            print(f"\n🤖 Generated Code:")
            print("```python")
            print(code)
            print("```")

            # Ask for user confirmation
            confirm = input("\n👤 Execute this code? (yes/no): ").strip().lower()

            if confirm not in ['yes', 'y']:
                return False, "⏩ Code execution cancelled by user."

            # Execute the code
            success, output, updated_df = self.repl_executor.execute_code(code)

            if success:
                # Log the execution
                self.execution_history.append({
                    "instruction": user_instruction,
                    "code": code,
                    "output": output,
                    "timestamp": time.time()
                })

                return True, f"✅ Code executed successfully!\n📄 Output: {output}"
            else:
                return False, f"❌ Code execution failed: {output}"

        except Exception as e:
            error_msg = f"Error processing instruction: {str(e)}"
            logger.error(error_msg)
            return False, f"❌ {error_msg}"

    def show_current_state(self):
        """Show current DataFrame state"""
        current_df = self.repl_executor.get_current_dataframe()
        print(f"\n📊 Current DataFrame State:")
        print(f"   Shape: {current_df.shape}")
        print(f"   Columns: {list(current_df.columns)}")
        print("\n🔍 Preview (first 5 rows):")
        print(current_df.head(5).to_string(index=False))

    def save_data(self, filename: Optional[str] = None):
        """Save current DataFrame state"""
        os.makedirs(self.out_dir, exist_ok=True)

        if not filename:
            filename = "enhanced_conversational_output.parquet"

        file_path = os.path.join(self.out_dir, filename)
        current_df = self.repl_executor.get_current_dataframe()

        # Save DataFrame
        if filename.endswith('.parquet'):
            current_df.to_parquet(file_path, index=False)
        elif filename.endswith('.csv'):
            current_df.to_csv(file_path, index=False)
        else:
            # Default to parquet
            file_path += '.parquet'
            current_df.to_parquet(file_path, index=False)

        # Save execution history
        history_path = os.path.join(self.out_dir, "execution_history.json")
        with open(history_path, "w") as f:
            json.dump(self.execution_history, f, indent=2)

        print(f"💾 Data saved to: {file_path}")
        print(f"📝 Execution history saved to: {history_path}")

    def chat_loop(self):
        """Main conversational loop"""
        print("\n🚀 Enhanced Conversational Data Agent with Python REPL")
        print("="*60)
        print("💬 Chat with your data using natural language!")
        print("🐍 I'll generate and execute Python code based on your instructions.")
        print("\n📋 Available commands:")
        print("  • 'show' or 'preview' - Show current DataFrame state")
        print("  • 'save [filename]' - Save current data")
        print("  • 'history' - Show execution history")
        print("  • 'reset' - Reset to original data")
        print("  • 'exit' or 'quit' - End session")
        print("="*60)

        while True:
            try:
                user_input = input("\n👤 You: ").strip()

                if not user_input:
                    continue

                user_lower = user_input.lower()

                # Handle special commands
                if user_lower in ['exit', 'quit']:
                    print("👋 Goodbye! Session ended.")
                    break

                elif user_lower in ['show', 'preview']:
                    self.show_current_state()
                    continue

                elif user_lower.startswith('save'):
                    parts = user_input.split(maxsplit=1)
                    filename = parts[1] if len(parts) > 1 else None
                    self.save_data(filename)
                    continue

                elif user_lower == 'history':
                    print(f"\n📜 Execution History ({len(self.execution_history)} items):")
                    for i, item in enumerate(self.execution_history[-5:], 1):  # Show last 5
                        print(f"{i}. {item['instruction'][:50]}...")
                    continue

                elif user_lower == 'reset':
                    self.repl_executor = PythonREPLExecutor(self.df_original)
                    print("🔄 DataFrame reset to original state.")
                    continue

                # Process natural language instruction
                print(f"\n🤔 Processing: {user_input}")
                success, response = self.process_user_instruction(user_input)
                print(f"\n🤖 {response}")

                if success:
                    # Optionally show brief state after successful operations
                    current_df = self.repl_executor.get_current_dataframe()
                    print(f"📊 Current shape: {current_df.shape}")

            except KeyboardInterrupt:
                print("\n\n👋 Session interrupted. Goodbye!")
                break
            except Exception as e:
                logger.error("Error in chat loop: %s", e)
                print(f"❌ An error occurred: {e}")

# ---------------- CLI ----------------

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Enhanced Conversational ETL Agent with Python REPL")
    parser.add_argument("--input", required=True, help="Input CSV file path")
    parser.add_argument("--outdir", default="./data/out/enhanced_chat",
                       help="Output directory for results")

    args = parser.parse_args()

    try:
        # Create and run the enhanced agent
        agent = EnhancedConversationalETLAgent(args.input, args.outdir)
        agent.chat_loop()

    except Exception as e:
        print(f"❌ Error initializing agent: {e}")
        print("Make sure all dependencies are installed and GOOGLE_API_KEY is set in .env file")
