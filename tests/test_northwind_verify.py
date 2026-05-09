import pytest
from pathlib import Path
from unittest.mock import patch

from src.pipeline.northwind_verify import verify_northwind_hash


class TestNorthwindVerify:
    def test_verify_passes_with_correct_hash(self):
        # No deberia lanzar excepcion con el archivo correcto
        verify_northwind_hash()

    def test_verify_fails_with_wrong_hash(self, tmp_path):
        # Crear un hash file con valor incorrecto
        bad_hash_file = tmp_path / "northwind.db.sha256"
        bad_hash_file.write_text(
            "0000000000000000000000000000000000000000000000000000000000000000"
        )

        with patch(
            "src.pipeline.northwind_verify.config.SOURCE_DB_HASH_PATH",
            str(bad_hash_file),
        ):
            with pytest.raises(RuntimeError, match="Hash mismatch"):
                verify_northwind_hash()

    def test_verify_fails_when_db_missing(self, tmp_path):
        bad_db_path = tmp_path / "nonexistent.db"
        with patch(
            "src.pipeline.northwind_verify.config.SOURCE_DB_PATH", str(bad_db_path)
        ):
            with pytest.raises(RuntimeError, match="no encontrado"):
                verify_northwind_hash()

    def test_verify_fails_when_hash_file_missing(self, tmp_path):
        bad_hash_path = tmp_path / "nonexistent.sha256"
        with patch(
            "src.pipeline.northwind_verify.config.SOURCE_DB_HASH_PATH",
            str(bad_hash_path),
        ):
            with pytest.raises(RuntimeError, match="no encontrado"):
                verify_northwind_hash()
