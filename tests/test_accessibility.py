"""Keyboard affordances that are easy to lose in a visual-only check."""
from pathlib import Path


def test_overflowing_result_tables_are_keyboard_focusable(client):
    for path in ("/replay", "/evidence", "/dashboard"):
        html = client.get(path).data.decode()
        assert 'class="table-wrap" tabindex="0" role="region" aria-label=' in html, path


def test_crew_selector_uses_button_pressed_state_not_tab_selection_state():
    source = (Path(__file__).resolve().parents[1] / "app/static/js/dashboard.js").read_text()
    assert 'aria-pressed' in source
    assert 'aria-selected' not in source
