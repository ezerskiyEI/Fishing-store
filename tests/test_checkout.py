# tests/test_checkout.py
def test_checkout_requires_login(client):
    """Неавторизованный пользователь должен быть перенаправлен на логин"""
    response = client.get("/checkout", follow_redirects=True)
    html = response.data.decode('utf-8')
    assert "Вход" in html or "Войти" in html


def test_checkout_with_valid_cart(client, db_session):
    """Полноценный тест оформления заказа"""
    # Создаём пользователя
    user = User(username="buyer", email="buyer@test.com", password="123", is_admin=False)
    db_session.add(user)
    db_session.commit()

    # Логиним пользователя
    with client.session_transaction() as sess:
        sess["_user_id"] = str(user.id)

    # Добавляем товар в БД
    product = Product(name="Тестовый спиннинг", price=450.0, category="Спиннинговые удилища")
    db_session.add(product)
    db_session.commit()

    # Добавляем товар в корзину
    client.get(f"/add_to_cart/{product.id}")

    # Оформляем заказ
    response = client.post("/checkout", data={
        "delivery_type": "pickup",
        "city": "Минск",
        "notification_method": "email"
    }, follow_redirects=True)

    html = response.data.decode('utf-8')

    assert response.status_code == 200
    assert "Заказ оформлен" in html or "успешно" in html or "профиль" in html.lower()