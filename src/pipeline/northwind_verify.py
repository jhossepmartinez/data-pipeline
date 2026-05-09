import hashlib
import logging
from pathlib import Path

from src.config import config

logger = logging.getLogger(__name__)


def _compute_sha256(file_path: Path) -> str:
    """Calcula el SHA-256 de un archivo."""
    h = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def verify_northwind_hash() -> None:
    """
    Verifica que el hash SHA-256 de northwind.db coincida con el valor esperado.

    Raises:
        RuntimeError: si el archivo de hash esperado no existe o los hashes no coinciden.
    """
    db_path = Path(config.SOURCE_DB_PATH).resolve()
    hash_file = Path(config.SOURCE_DB_HASH_PATH).resolve()

    if not db_path.exists():
        logger.error("Northwind DB no encontrado: %s", db_path)
        raise RuntimeError(
            f"Northwind DB no encontrado: {db_path}\n"
            "Descargalo desde: https://raw.githubusercontent.com/jpwhite3/northwind-SQLite3/"
            "4f56e7f5906dfd23b25244c5bfe8fb5da6402efd/dist/northwind.db"
        )

    if not hash_file.exists():
        logger.error("Archivo de hash esperado no encontrado: %s", hash_file)
        raise RuntimeError(
            f"Archivo de hash esperado no encontrado: {hash_file}\n"
            "Asegurate de que el repo incluya data/raw/northwind.db.sha256"
        )

    expected_hash = hash_file.read_text().strip().split()[0]
    actual_hash = _compute_sha256(db_path)

    if expected_hash != actual_hash:
        logger.error(
            "Hash mismatch para Northwind DB.\n"
            "  Esperado: %s\n"
            "  Actual:   %s\n"
            "  Archivo:  %s",
            expected_hash,
            actual_hash,
            db_path,
        )
        raise RuntimeError(
            f"Hash mismatch para Northwind DB.\n"
            f"  Esperado: {expected_hash}\n"
            f"  Actual:   {actual_hash}\n"
            f"El archivo descargado no coincide con la version esperada. "
            f"Descargalo desde: https://raw.githubusercontent.com/jpwhite3/"
            f"northwind-SQLite3/4f56e7f5906dfd23b25244c5bfe8fb5da6402efd/dist/northwind.db"
        )

    logger.info("Northwind DB verificado correctamente. Hash: %s", actual_hash)
