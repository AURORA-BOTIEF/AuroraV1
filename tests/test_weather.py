import re
import pytest
import importlib.util
from pathlib import Path

# Load the project-top-level weather_module.py by path so pytest collection
# (which changes sys.path) doesn't interfere with importing from the project root.
root = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("weather_module", str(root / "weather_module.py"))
weather_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(weather_module)


def test_get_current_weather_basic():
    loc = "San Francisco"
    out = weather_module.get_current_weather(loc)
    assert isinstance(out, dict)
    assert out["location"] == loc
    assert "temperature_c" in out and isinstance(out["temperature_c"], (int, float))
    assert out["condition"] == "Sunny"
    assert out["source"] == "local_stub"
    # observed_at should be an ISO timestamp ending with Z
    assert isinstance(out.get("observed_at"), str)
    assert out["observed_at"].endswith("Z")


def test_get_current_weather_empty_location():
    with pytest.raises(ValueError):
        weather_module.get_current_weather("")


def test_observed_at_format():
    out = weather_module.get_current_weather("X")
    iso = out["observed_at"]
    # basic ISO format check
    assert re.match(r"^\d{4}-\d{2}-\d{2}T", iso)
