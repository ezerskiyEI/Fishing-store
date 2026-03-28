def test_user_model(db_session):
    user = User(username="testuser", email="test@example.com", password="hashed")
    db_session.add(user)
    db_session.commit()

    assert user.id is not None
    assert User.query.filter_by(username="testuser").first() is not None


def test_product_model(db_session):
    product = Product(
        name="Спиннинг Shimano",
        price=299.90,
        category="Спиннинговые удилища",
        description="Отличный спиннинг",
        old_price=350.0
    )
    db_session.add(product)
    db_session.commit()

    assert product.id is not None
    assert product.old_price == 350.0