# Enhanced Conversational ETL Agent with Python REPL

An **experimental conversational ETL (Extract–Transform–Load) agent** that allows you to interact with CSV data using natural language. The agent uses:

* **LangChain’s PythonAstREPLTool** for dynamic Python code execution
* **Google Gemini LLM** to generate transformation code
* **Presidio** for PII (Personally Identifiable Information) scrubbing
* **pandas** for data analysis and transformation

This is the **first working version** of the tool.

---

## Features

* Conversational interface to manipulate your data
* Generates and executes Python code based on user instructions
* Maintains DataFrame state across the conversation
* Supports preview, saving, and resetting the dataset
* Execution history logging
* PII scrubbing utilities

---

## Installation

1. Clone this repository or download the script.
2. Install dependencies:

   ```bash
   pip install langchain langchain-experimental pandas pyarrow presidio-analyzer presidio-anonymizer python-dotenv google-generativeai spacy scikit-learn
   python -m spacy download en_core_web_lg
   ```
3. Set your **Google Gemini API key** in a `.env` file:

   ```env
   GOOGLE_API_KEY=your_api_key_here
   ```

---

## Usage

Run the agent from the command line:

```bash
python enhanced_agent_with_repl.py --input path/to/input.csv --outdir ./data/out/enhanced_chat
```

### Chat Commands

* `show` / `preview` → Show current DataFrame state
* `save [filename]` → Save the current DataFrame (CSV or Parquet)
* `history` → Show execution history
* `reset` → Reset to original data
* `exit` / `quit` → End session

The agent will:

1. Load your CSV file
2. Display a preview
3. Accept natural language instructions (e.g., *"drop rows with null values"*)
4. Generate Python code, ask for confirmation, then execute

---

## Example Flow

````
👤 You: drop rows where age is null
🤖 Generated Code:
```python
df = df.dropna(subset=['age'])
print(f"Shape after dropping: {df.shape}")
````

👤 Execute this code? (yes/no): yes
✅ Code executed successfully!

```

---

## Current Limitations / Shortcomings
This is the first basic version (working). The following improvements are still needed:

1. Ability to load and save other DataFrames from already saved files.
2. If the user asks for it, provide results in a DataFrame (not just prints) that can be saved.
3. Two save options explicitly supported: **CSV** and **Parquet**.
4. Agent should remember the full history across sessions (currently resets per run).
5. A **glossarizer command** to share overview/summary of the data.
6. Multiple input files may not work properly yet.

---

## Roadmap
- [ ] Add DataFrame switching/loading functionality
- [ ] Save and reload conversational + execution history
- [ ] Implement `glossarizer` for quick data overview
- [ ] Better multi-file support

---

## License
This project is experimental and provided as-is for educational use.

```

