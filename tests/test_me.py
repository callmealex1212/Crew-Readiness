"""The crew-first page: it loads, it is wired to the right data, and it never talks about health or cause."""
import re


def test_me_page_renders_and_is_in_the_nav(client):
    html = client.get("/me").data.decode()
    assert "Your own status, first." in html and 'href="/me"' in html
    assert 'id="me-select"' in html and "js/me.js" in html
    assert "Privacy &amp; limits" in html                          # the sharing proposal points to the limits page


def test_me_page_makes_no_health_or_cause_claim(client):
    html = re.sub(r"<[^>]+>", " ", client.get("/me").data.decode()).lower()
    assert "cannot tell which one it is" in html and "says nothing about your health" in html
    for w in ("diagnos", "unfit", "impaired", "fatigued", "your health is", "you are tired"):
        assert w not in html


def test_the_data_the_page_reads_exists_for_every_profile(client):
    profiles = client.get("/api/profiles").get_json()["profiles"]
    assert profiles
    for p in profiles:
        r = client.get(f"/api/readiness/{p['id']}").get_json()["readiness"]
        assert r["status"] in ("SCORED", "CALIBRATING", "INSUFFICIENT_DATA") and "baseline_needed" in r


def test_mission_page_has_the_no_ground_link_section(client):
    html = client.get("/mission").get_data(as_text=True)
    assert 'id="no-ground-link"' in html and "Not tested" in html and 'href="/me"' in html
