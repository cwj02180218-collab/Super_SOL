from fablized_sol.engine.classify_task import classify_prompt
from fablized_sol.engine.models import TaskMode


def test_classifies_database_migration_as_deep() -> None:
    result = classify_prompt("프로덕션 DB 마이그레이션을 구현하고 검증해줘")
    assert result.mode is TaskMode.DEEP
    assert result.risk_flags == ("database",)


def test_classifies_lowercase_db_with_korean_migration_as_deep() -> None:
    assert classify_prompt("db 마이그레이션을 구현해줘").mode is TaskMode.DEEP


def test_classifies_explanation_as_quick() -> None:
    assert classify_prompt("이 함수가 뭐야?").mode is TaskMode.QUICK
