# tests/test_admin.py
def test_admin_access_denied_for_regular_user(client, db_session):
    """Обычный пользователь не должен попасть в админку"""
    # Создаём обычного пользователя
    user = User(username="regular", email="regular@test.com", password="123", is_admin=False)
    db_session.add(user)
    db_session.commit()

    # Логиним обычного пользователя
    with client.session_transaction() as sess:
        sess["_user_id"] = str(user.id)

    response = client.get("/admin", follow_redirects=True)
    html = response.data.decode('utf-8')
    assert "Доступ запрещен" in html or "Вход" in html


def test_admin_access_allowed_for_admin(client, db_session):
    """Администратор должен попасть в панель"""
    admin = User(username="admin", email="admin@test.com", password="123", is_admin=True)
    db_session.add(admin)
    db_session.commit()

    with client.session_transaction() as sess:
        sess["_user_id"] = str(admin.id)

    response = client.get("/admin", follow_redirects=True)
    html = response.data.decode('utf-8')
    assert "Панель администратора" in html or "Управление товаром" in html