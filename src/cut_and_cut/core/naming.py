import re
from pathlib import Path

_INVALID = set('\\/:*?"<>|')
_RESERVED = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    *(f"COM{n}" for n in range(1, 10)),
    *(f"LPT{n}" for n in range(1, 10)),
}
_COLLAPSE = re.compile(r"_+")
_MAX_COMPONENT = 60


def sanitize_component(text: str, *, fallback: str, max_length: int = _MAX_COMPONENT) -> str:
    """Make one path component safe on Windows and macOS.

    Accents stay. Spaces and characters that are illegal in file names become
    underscores. The result is trimmed so a long title cannot blow the path.
    """
    cleaned = "".join(_clean_char(char) for char in text.strip())
    cleaned = _COLLAPSE.sub("_", cleaned).strip("._ ")
    cleaned = cleaned[:max_length].rstrip("._ ")
    if not cleaned:
        cleaned = fallback
    if _is_reserved(cleaned):
        cleaned = f"{cleaned}_arquivo"
        cleaned = cleaned[:max_length].rstrip("._ ")
    return cleaned or fallback


def build_output_path(
    destination: Path,
    project_name: str,
    index: int,
    title: str,
    extension: str,
) -> Path:
    """Return ``<destination>/<project>/<project>_NN_<title>.<ext>``.

    Isolated so the naming scheme can change without touching the exporter.
    """
    project = sanitize_component(project_name, fallback="projeto")
    safe_title = sanitize_component(title, fallback="corte")
    ext = normalize_extension(extension)
    filename = f"{project}_{index:02d}_{safe_title}{ext}"
    return destination / project / filename


def normalize_extension(extension: str) -> str:
    suffix = extension.strip().lstrip(".").lower()
    suffix = "".join(char for char in suffix if char.isalnum())
    return f".{suffix or 'mp4'}"


def _clean_char(char: str) -> str:
    if char in _INVALID or ord(char) < 32 or char.isspace():
        return "_"
    return char


def _is_reserved(name: str) -> bool:
    stem = name.split(".", 1)[0]
    return stem.upper() in _RESERVED
