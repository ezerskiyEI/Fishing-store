# tests/test_auth.py
def test_register(client, db_session):
    response = client.post("/register", data={
        "username": "newuser",
        "email": "newuser@test.com",
        "password": "password123"
    }, follow_redirects=True)
    
    assert response.status_code in (200, 302)
    html = response.data.decode('utf-8')
    assert "Код" in html or "Регистрация" in html


def test_login_success(client, db_session):
    user = User(username="loginuser", email="login@test.com", password="hashedpass123")
    db_session.add(user)
    db_session.commit()

    response = client.post("/login", data={
        "login_identity": "loginuser",
        "password": "hashedpass123"
    }, follow_redirects=True)
    
    html = response.data.decode('utf-8')
    assert "Профиль" in html