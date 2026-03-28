def test_assistant_api(client):
    response = client.post("/api/assistant", json={
        "message": "Какая катушка лучше для спиннинга?",
        "session_id": "test123"
    })
    assert response.status_code == 200
    assert "response" in response.get_json()