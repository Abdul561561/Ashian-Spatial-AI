from typing import Dict, List, Optional, Any
from src.database.db_manager import DatabaseManager
from src.ai_assistant.query_engine import SpatialQueryEngine
from src.ai_assistant.openrouter_client import OpenRouterClient

class AshianSpatialAssistant:
    """Conversational architectural assistant providing verified, evidence-backed answers."""

    SAMPLE_QUESTIONS = [
        "How many rooms are in this floor plan?",
        "What is the largest room by area?",
        "What is the smallest room by area?",
        "List all rooms with their functional types and areas.",
        "How many doors and windows were detected?",
        "What rooms are directly connected to Room 1?",
        "Which door connects Room 1 and Room 4?",
        "Are there any entrance doors opening to the outside?",
        "What is the extraction confidence score and validation status?",
        "What is the area of the Living Room in square meters?",
        "Can you show me all bathroom or service spaces?",
        "What is the total indoor pixel area of the building?",
    ]

    def __init__(self, db_manager: DatabaseManager):
        self.db_manager = db_manager
        self.client = OpenRouterClient()
        self.engine = SpatialQueryEngine(db_manager=self.db_manager, llm_client=self.client)
        self.history: List[Dict[str, Any]] = []

    def ask(self, question: str, active_plan_id: Optional[str] = "1") -> Dict[str, Any]:
        """Processes a question and stores the exchange in conversation history."""
        response = self.engine.answer_question(question=question, active_plan_id=active_plan_id)
        
        # Save to chat history
        self.history.append({
            "question": question,
            "active_plan_id": active_plan_id,
            "response": response,
        })

        return response

    def clear_history(self) -> None:
        """Clears local session conversation history."""
        self.history = []
