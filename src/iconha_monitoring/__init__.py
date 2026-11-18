from pathlib import Path
import tomllib


def get_version() -> str:
    """Reads the semantic version from pyproject.toml."""
    try:
        pyproject_path = Path(__file__).resolve().parents[2] / "pyproject.toml"
        with open(pyproject_path, "rb") as f:
            data = tomllib.load(f)
            return data["project"]["version"]
    except Exception:
        return "2.0.0"


__version__ = get_version()