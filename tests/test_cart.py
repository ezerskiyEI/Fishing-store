# tests/test_cart.py
def test_add_to_cart(client, db_session):
    p = Product(name="Воблер", price=120)
    db_session.add(p)
    db_session.commit()

    response = client.get(f"/add_to_cart/{p.id}", follow_redirects=True)
    html = response.data.decode('utf-8')
    assert "Товар добавлен" in html


def test_cart_page(client, db_session):
    p = Product(name="Тестовый товар", price=200)
    db_session.add(p)
    db_session.commit()

    client.get(f"/add_to_cart/{p.id}")
    response = client.get("/cart")
    html = response.data.decode('utf-8')
    assert "Тестовый товар" in html