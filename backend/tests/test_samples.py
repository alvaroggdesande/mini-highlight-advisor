from fastapi.testclient import TestClient
from mini_highlight_advisor import samples
from backend.main import app

client = TestClient(app)

def test_list_samples_matches_core():
    r = client.get("/api/samples/photos")
    assert r.status_code == 200
    assert len(r.json()) == len(samples.list_photos())

def test_fetch_first_sample_bytes():
    photos = samples.list_photos()
    if not photos:
        import pytest; pytest.skip("no bundled sample photos")
    sid = photos[0].path.stem
    r = client.get(f"/api/samples/photos/{sid}")
    assert r.status_code == 200 and r.content[:4] in (b"\x89PNG", b"\xff\xd8\xff\xe0")

def test_unknown_sample_404():
    assert client.get("/api/samples/photos/nope-not-real").status_code == 404
