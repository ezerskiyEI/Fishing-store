# tests/test_routes.py
def test_index_page(client):
    response = client.get("/")
    assert response.status_code == 200
    html = response.data.decode('utf-8')
    assert "Золотая рыбка" in html


def test_catalog(client, db_session):
    p = Product(name="Катушка Daiwa", price=450, category="Катушки")
    db_session.add(p)
    db_session.commit()

    response = client.get("/catalog?search=Катушка")
    html = response.data.decode('utf-8')
    assert "Катушка Daiwa" in html


def test_promotions(client, db_session):
    p = Product(name="Акционный товар", price=100, old_price=150)
    db_session.add(p)
    db_session.commit()

    response = client.get("/promotions")
    html = response.data.decode('utf-8')
    assert "Акционный товар" in html