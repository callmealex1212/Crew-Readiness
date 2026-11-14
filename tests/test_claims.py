"""Claims audit (task V-3), automated: what the product and README say must stay inside docs/PLAN.md section 1."""
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
PAGES = ["/", "/dashboard", "/monitor", "/attention", "/mission", "/replay", "/evidence", "/about"]
TOUCHY = re.compile(r"fatigue|impair|cognitive|illness|unfit|diagnos|fitness for duty", re.I)
DENIES = re.compile(r"\bnot\b|\bno\b|\bnever\b|\bnothing\b|\bnor\b|\bwithout\b|\bsays nothing\b|\bdoes not\b", re.I)
BANNED = ("% accurate", "accuracy of", "proven to", "guaranteed", "ai-powered", "clinically proven", "cleared for duty")


def text_of(html: str) -> str:
    html = re.sub(r"<(script|style)[\s\S]*?</\1>", " ", html)
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html))


def sentences(text: str):
    return [s for s in re.split(r"(?<=[.!?])\s+", text) if s.strip()]


def all_texts(client):
    out = {p: text_of(client.get(p).data.decode()) for p in PAGES}
    out["README.md"] = (ROOT / "README.md").read_text(encoding="utf-8")
    out["docs/SUBMISSION.md"] = (ROOT / "docs" / "SUBMISSION.md").read_text(encoding="utf-8")
    return out


def test_touchy_words_only_appear_in_a_sentence_that_denies_them(client):
    bad = [(name, s.strip()[:110]) for name, t in all_texts(client).items() for s in sentences(t)
           if TOUCHY.search(s) and not DENIES.search(s)]
    assert not bad, f"affirmative-sounding mention of a medical or fitness claim: {bad}"


def test_no_banned_overclaim_phrases(client):
    bad = [(name, b) for name, t in all_texts(client).items() for b in BANNED if b in t.lower()]
    assert not bad, bad


def test_nasa_is_never_claimed_as_approver_or_partner(client):
    for name, t in all_texts(client).items():
        for s in sentences(t):
            if re.search(r"NASA[- ](approved|endorsed|partner|certified)", s, re.I):
                assert DENIES.search(s), (name, s[:110])


@pytest.mark.parametrize("path", ["/", "/dashboard", "/monitor", "/replay", "/evidence"])
def test_no_unfinished_todo_text_on_finished_pages(client, path):
    assert "TODO" not in text_of(client.get(path).data.decode())


@pytest.mark.xfail(reason="R-1 (privacy page) is still being built; see docs/NEXT_STEPS.md", strict=False)
def test_no_unfinished_todo_text_on_about_page_still_being_built(client):
    assert "TODO" not in text_of(client.get("/about").data.decode())


def test_attention_page_has_no_unfinished_todo_text(client):
    assert "TODO" not in text_of(client.get("/attention").data.decode())


@pytest.mark.xfail(reason="L-1 (mission_advisory) is being implemented by the team lead", strict=False)
def test_mission_advisory_is_implemented(client):
    assert client.get("/api/mission").get_json()["advisory"]["level"] != "TODO"
