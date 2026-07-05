from fastapi.testclient import TestClient

PNG_BYTES = (
    b"\x89PNG\r\n\x1a\n"
    b"\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde"
    b"\x00\x00\x00\x0cIDAT\x08\xd7c\xf8\x0f\x00\x01\x01\x01\x00\x18\xdd\x8d\xb1"
    b"\x00\x00\x00\x00IEND\xaeB`\x82"
)


def make_client(tmp_path, monkeypatch) -> TestClient:
    from app import main as main_module

    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "og.png").write_bytes(PNG_BYTES)
    (dist / "index.html").write_text("<!doctype html><html><body>SPA</body></html>")
    monkeypatch.setattr(main_module, "SPA_DIST", dist)
    return TestClient(main_module.create_app())


def test_spa_root_metadata_image_is_served_as_file(tmp_path, monkeypatch):
    with make_client(tmp_path, monkeypatch) as client:
        response = client.get("/og.png")

    assert response.status_code == 200
    assert response.headers["content-type"] == "image/png"


def test_spa_route_falls_back_to_index_html(tmp_path, monkeypatch):
    with make_client(tmp_path, monkeypatch) as client:
        response = client.get("/some/client/route")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
