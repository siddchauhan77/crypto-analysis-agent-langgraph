"""Static checks for the public composite analyst demo boundary."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_composite_analyst_documentation_has_sources_and_explicit_limits() -> None:
    scenario = (ROOT / "docs" / "customer-simulation.md").read_text()

    assert "fictional composite" in scenario
    assert "does not prove demand, adoption" in scenario
    assert "https://jobs.ashbyhq.com/allium/" in scenario
    assert "https://jobs.ashbyhq.com/elliptic/" in scenario
    assert "https://www.binance.com/en/research" in scenario
    assert "Do not make a trading recommendation." in scenario


def test_public_interface_exposes_the_composite_analyst_prompt() -> None:
    interface = (ROOT / "public" / "index.html").read_text()

    assert "Run analyst brief" in interface
    assert "Composite scenario" in interface
    assert "Do not make a trading recommendation." in interface
