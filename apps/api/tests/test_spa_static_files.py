def test_spa_root_metadata_image_is_served_as_file(client):
    response = client.get("/og.png")

    assert response.status_code == 200
    assert response.headers["content-type"] == "image/png"


def test_spa_route_falls_back_to_index_html(client):
    response = client.get("/some/client/route")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
