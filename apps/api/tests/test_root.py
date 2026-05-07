def test_root_returns_404_until_dashboard_lands(client):
    response = client.get("/")

    assert response.status_code == 404
