from app import app, db, Product
import os
from pathlib import Path

with app.app_context():
    folder = Path('static/uploads')
    for file in folder.glob('*.*'):
        if file.name == 'no_image.png':
            continue
        try:
            prod_id = int(file.stem)
            prod = Product.query.get(prod_id)
            if not prod:
                continue
                
            with open(file, 'rb') as f:
                result = cloudinary.uploader.upload(
                    f,
                    folder="fishing-shop/products/old",
                    resource_type="image"
                )
            
            prod.image_url = result['secure_url']
            prod.image_public_id = result['public_id']
            db.session.commit()
            print(f"Успешно: {prod_id} → {result['secure_url']}")
        except Exception as e:
            print(f"Ошибка {file.name}: {e}")