import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.database.db_manager import DatabaseManager
from src.ai_assistant.query_engine import SpatialQueryEngine

db = DatabaseManager()
engine = SpatialQueryEngine(db_manager=db)

# Force rule engine for fast deterministic verification, or test both
questions = [
    ("How many rooms does plan 12 have?", "12"),
    ("What is the largest room in plan 7?", "7"),
    ("Which plans have more than 3 doors?", None),
    ("Which room in plan 4 has no windows?", "4"),
    ("What is the average number of rooms across all plans?", None),
    ("Who is the architect of building 1?", "1"),  # Unsupported question
    ("What is the construction cost of floor plan 2?", "2"),  # Unsupported question
    ("What is the area of the living room in square meters?", "1"),  # Scale calibration question
]

print("=== Testing Assignment & Benchmark Questions ===\n", flush=True)
for i, (q, pid) in enumerate(questions, start=1):
    print(f"[{i}] Question: '{q}' (active_plan_id={pid})", flush=True)
    res = engine.answer_question(q, active_plan_id=pid)
    print(f"    Success:    {res['success']}", flush=True)
    print(f"    Confidence: {res.get('confidence')}", flush=True)
    print(f"    SQL:        {res.get('generated_sql')}", flush=True)
    print(f"    Records:    {res.get('record_count', len(res.get('records', [])))}", flush=True)
    print(f"    Answer:     {res.get('answer')[:120]}...\n", flush=True)
