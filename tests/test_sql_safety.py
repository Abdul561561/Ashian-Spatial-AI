import pytest
from src.ai_assistant.sql_validator import SQLValidator

def test_sql_validator_accepts_valid_queries():
    val = SQLValidator()
    
    valid_queries = [
        "SELECT * FROM rooms",
        "SELECT room_name, pixel_area FROM rooms WHERE room_type = 'Living Room'",
        "SELECT fp.plan_id, COUNT(r.id) FROM floor_plans fp JOIN rooms r ON fp.id = r.floor_plan_id GROUP BY fp.plan_id",
        "SELECT * FROM doors WHERE is_entrance = 1",
        "SELECT * FROM room_connections WHERE distance_px > 100",
        "SELECT num_rooms, validation_status FROM extraction_metadata",
    ]

    for q in valid_queries:
        is_val, clean = val.validate_sql(q)
        assert is_val is True, f"Valid query rejected: {q} -> {clean}"
        assert "LIMIT" in clean, "Validator should ensure a safety LIMIT"

def test_sql_validator_blocks_destructive_operations():
    val = SQLValidator()

    malicious_queries = [
        "DROP TABLE rooms",
        "DELETE FROM rooms WHERE id = 1",
        "UPDATE rooms SET pixel_area = 0",
        "INSERT INTO rooms (room_name) VALUES ('Hacked')",
        "ALTER TABLE rooms ADD COLUMN secret TEXT",
        "TRUNCATE TABLE rooms",
        "PRAGMA table_info(rooms)",
        "ATTACH DATABASE 'evil.db' AS evil",
        "VACUUM",
    ]

    for q in malicious_queries:
        is_val, reason = val.validate_sql(q)
        assert is_val is False, f"Malicious query was not blocked: {q}"
        assert "Security Violation" in reason

def test_sql_validator_blocks_multi_statement_injection():
    val = SQLValidator()

    injection_queries = [
        "SELECT * FROM rooms; DROP TABLE rooms;",
        "SELECT * FROM rooms; DELETE FROM doors;",
        "SELECT 1; SELECT 2;",
    ]

    for q in injection_queries:
        is_val, reason = val.validate_sql(q)
        assert is_val is False, f"Multi-statement injection was not blocked: {q}"
        assert "Multiple SQL statements" in reason

def test_sql_validator_blocks_unauthorized_tables():
    val = SQLValidator()

    unauthorized_queries = [
        "SELECT * FROM users",
        "SELECT * FROM credentials",
        "SELECT * FROM sqlite_master",
        "SELECT * FROM system_accounts",
    ]

    for q in unauthorized_queries:
        is_val, reason = val.validate_sql(q)
        assert is_val is False, f"Unauthorized table query not blocked: {q}"
        assert "forbidden" in reason.lower()
