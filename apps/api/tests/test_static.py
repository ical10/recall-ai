def test_static_responses_include_cache_control_header(client):
    response = client.get("/static/css/input.css")

    assert response.status_code == 200
    assert response.headers["cache-control"] == "public, max-age=300"
