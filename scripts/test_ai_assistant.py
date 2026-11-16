import sys
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.database.db_manager import DatabaseManager
from src.ai_assistant.assistant import AshianSpatialAssistant
from src.ai_assistant.sql_validator import SQLValidator

def main():
    print("=== Testing Ashian Spatial AI Assistant & OpenRouter ===", flush=True)
    db = DatabaseManager()
    assistant = AshianSpatialAssistant(db_manager=db)

    print(f"OpenRouter Configured: {assistant.client.is_configured()}", flush=True)
    print(f"Model: {assistant.client.model}", flush=True)

    test_queries = [
        "How many rooms are in floor plan 1?",
        "What is the largest room by area in floor plan 1?",
        "What rooms connect to Room 1?",
        "What is the area of the Living Room in square meters?", # Should warn about scale!
    ]

    for q in test_queries:
        print(f"\n--- Question: '{q}' ---", flush=True)
        resp = assistant.ask(q, active_plan_id="1")
        print(f"Success: {resp['success']}", flush=True)
        print(f"Model/Method: {resp.get('generation_method')} ({resp.get('model_used')})", flush=True)
        print(f"Generated SQL: {resp.get('generated_sql')}", flush=True)
        print(f"Records Count: {resp.get('record_count')}", flush=True)
        print(f"Answer: {resp.get('answer')}", flush=True)

    # Test Security Blocking
    print("\n=== Testing SQL Security Validator ===", flush=True)
    malicious = [
        "DROP TABLE rooms;",
        "SELECT * FROM rooms; DELETE FROM rooms;",
        "SELECT * FROM users", # Unauthorized table
        "UPDATE rooms SET pixel_area = 999999",
    ]
    val = SQLValidator()
    for m in malicious:
        is_val, msg = val.validate_sql(m)
        print(f"Query: '{m}' -> Allowed: {is_val} | Result: {msg}", flush=True)

if __name__ == "__main__":
    main()
