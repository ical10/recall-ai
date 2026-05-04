def test_index_renders_with_htmx_and_compiled_tailwind(client):
    response = client.get("/")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")

    body = response.text
    assert "RecallAI" in body
    assert "htmx.org" in body
    assert "/static/css/output.css" in body
    assert "cdn.tailwindcss.com" not in body
