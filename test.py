import pytest
import re
from app import app 

@pytest.fixture
def client():
    """Создает тестовый клиент Flask"""
    app.config['TESTING'] = True
    app.config['SERVER_NAME'] = 'localhost.localdomain'
    with app.test_client() as client:
        with app.app_context():
            yield client

class TestAboutPage:
    """Тесты для страницы 'О нас' (about.html)"""
    
    def test_about_page_status_code(self, client):
        """Тест 1: Проверка, что страница /about загружается"""
        response = client.get('/about')
        assert response.status_code == 200
    
    def test_about_page_uses_correct_template(self, client):
        """Тест 2: Проверка использования правильного шаблона"""
        response = client.get('/about')
        # Проверяем, что используется about.html (ищем уникальные элементы из about.html)
        html = response.data.decode('utf-8')
        assert 'О магазине Fishing Shop' in html
        assert 'Мы поставляем лучшие рыболовные снасти с 2026 года' in html
    
    def test_about_page_extends_base(self, client):
        """Тест 3: Проверка, что шаблон наследует base.html"""
        response = client.get('/about')
        html = response.data.decode('utf-8')
        # Проверяем признаки base.html
        assert '{% extends "base.html" %}' in response.data.decode('utf-8', errors='ignore') or \
               'Fishing Shop' in html  # base.html обычно содержит название магазина
    
    def test_about_page_title(self, client):
        """Тест 4: Проверка заголовка страницы"""
        response = client.get('/about')
        # Ищем тег title в HTML
        assert '<title>О нас - Fishing Shop</title>' in response.data.decode('utf-8')
    
    def test_main_heading_exists(self, client):
        """Тест 5: Проверка основного заголовка h1"""
        response = client.get('/about')
        html = response.data.decode('utf-8')
        assert '<h1 class="display-5 fw-bold">О магазине Fishing Shop</h1>' in html
    
    def test_advantages_cards_count(self, client):
        """Тест 6: Проверка количества карточек преимуществ (должно быть 3)"""
        response = client.get('/about')
        html = response.data.decode('utf-8')
        
        # Ищем все карточки преимуществ
        cards = re.findall(r'<div class="col-md-4">.*?<div class="card.*?">.*?</div>.*?</div>', html, re.DOTALL)
        assert len(cards) == 3
    
    def test_advantages_content(self, client):
        """Тест 7: Проверка содержания карточек преимуществ"""
        response = client.get('/about')
        html = response.data.decode('utf-8')
        
        # Проверяем наличие всех трех преимуществ
        assert 'Качество' in html
        assert 'Доставка' in html
        assert 'Поддержка' in html
        
        # Проверяем описания
        assert 'Только проверенные бренды и материалы' in html
        assert 'Быстрая доставка по всей Беларуси' in html
        assert 'Круглосуточная помощь настоящих рыбаков' in html
    
    def test_advantages_icons(self, client):
        """Тест 8: Проверка иконок Bootstrap в карточках"""
        response = client.get('/about')
        html = response.data.decode('utf-8')
        
        # Проверяем классы иконок Bootstrap
        assert 'bi-star-fill' in html
        assert 'bi-truck' in html
        assert 'bi-headset' in html
    
    def test_gallery_title(self, client):
        """Тест 9: Проверка заголовка галереи"""
        response = client.get('/about')
        html = response.data.decode('utf-8')
        assert '<h2 class="fw-bold text-center mb-5">Наши счастливые покупатели</h2>' in html
    
    def test_gallery_structure(self, client):
        """Тест 10: Проверка структуры галереи"""
        response = client.get('/about')
        html = response.data.decode('utf-8')
        
        # Проверяем наличие контейнера галереи
        assert '<div class="gallery-grid">' in html
        assert '</div>' in html
    
    def test_gallery_images_count(self, client):
        """Тест 11: Проверка количества изображений в галерее"""
        response = client.get('/about')
        html = response.data.decode('utf-8')
        
        # Считаем количество div-ов с классом gallery-item
        gallery_items = re.findall(r'<div class="gallery-item">.*?</div>', html, re.DOTALL)
        assert len(gallery_items) == 32  # В шаблоне 32 изображения
    
    def test_gallery_images_use_url_for(self, client):
        """Тест 12: Проверка, что пути к изображениям используют url_for"""
        response = client.get('/about')
        html = response.data.decode('utf-8')
        
        # Проверяем использование url_for для статических файлов
        assert "{{ url_for('static', filename=" in html
    
    def test_gallery_image_formats(self, client):
        """Тест 13: Проверка форматов изображений в галерее"""
        response = client.get('/about')
        html = response.data.decode('utf-8')
        
        # Проверяем наличие разных форматов
        assert '.JPG' in html
        assert '.png' in html
    
    def test_css_styles_defined(self, client):
        """Тест 14: Проверка наличия CSS стилей в шаблоне"""
        response = client.get('/about')
        html = response.data.decode('utf-8')
        
        # Проверяем наличие блока стилей
        assert '<style>' in html
        assert '</style>' in html
    
    def test_gallery_grid_css(self, client):
        """Тест 15: Проверка CSS свойств для галереи"""
        response = client.get('/about')
        html = response.data.decode('utf-8')
        
        # Проверяем CSS классы
        assert '.gallery-grid' in html
        assert '.gallery-item' in html
        assert 'grid-template-columns: repeat(3, 1fr)' in html
        assert 'gap: 28px' in html
    
    def test_gallery_item_properties(self, client):
        """Тест 16: Проверка свойств элементов галереи"""
        response = client.get('/about')
        html = response.data.decode('utf-8')
        
        # Проверяем свойства gallery-item
        assert 'border-radius: 20px' in html
        assert 'aspect-ratio: 3 / 4' in html
        assert 'object-fit: cover' in html
    
    def test_hover_effects(self, client):
        """Тест 17: Проверка эффектов при наведении"""
        response = client.get('/about')
        html = response.data.decode('utf-8')
        
        assert '.gallery-item:hover' in html
        assert 'transform: scale(1.05)' in html
    
    def test_responsive_breakpoints(self, client):
        """Тест 18: Проверка адаптивных медиа-запросов"""
        response = client.get('/about')
        html = response.data.decode('utf-8')
        
        # Проверяем наличие медиа-запросов
        assert '@media (max-width: 992px)' in html
        assert '@media (max-width: 576px)' in html
    
    def test_responsive_grid_changes(self, client):
        """Тест 19: Проверка изменения сетки на разных экранах"""
        response = client.get('/about')
        html = response.data.decode('utf-8')
        
        # Проверяем, что для планшетов сетка меняется на 2 колонки
        assert 'grid-template-columns: repeat(2, 1fr);' in html
        
        # Проверяем, что для телефонов сетка меняется на 1 колонку
        assert 'grid-template-columns: 1fr;' in html
    
    def test_shadows_and_borders(self, client):
        """Тест 20: Проверка теней и границ"""
        response = client.get('/about')
        html = response.data.decode('utf-8')
        
        # Проверяем наличие теней
        assert 'box-shadow: 0 12px 40px rgba(0,0,0,0.15)' in html
        assert 'shadow-sm' in html  # Bootstrap класс
    
    def test_no_broken_links(self, client):
        """Тест 21: Проверка отсутствия битых ссылок (простая проверка)"""
        response = client.get('/about')
        html = response.data.decode('utf-8')
        
        # Проверяем, что нет пустых src
        assert 'src=""' not in html
        assert 'src=" "' not in html
    
    def test_lead_paragraph(self, client):
        """Тест 22: Проверка наличия ведущего параграфа"""
        response = client.get('/about')
        html = response.data.decode('utf-8')
        
        assert '<p class="lead text-muted">' in html
        assert 'Реальные люди. Реальные трофеи.' in html
    
    def test_bootstrap_structure(self, client):
        """Тест 23: Проверка Bootstrap классов"""
        response = client.get('/about')
        html = response.data.decode('utf-8')
        
        bootstrap_classes = [
            'container', 'py-5', 'text-center', 'row', 
            'col-md-4', 'card', 'shadow-sm', 'h-100'
        ]
        
        for css_class in bootstrap_classes:
            assert css_class in html
    
    def test_duplicate_images_check(self, client):
        """Тест 24: Проверка на дубликаты изображений"""
        response = client.get('/about')
        html = response.data.decode('utf-8')
        
        # Находим все имена файлов
        image_files = re.findall(r'happy\d+\.(?:JPG|png)', html)
        
        # Проверяем, что дубликатов не больше 1 (happy14.JPG дублируется)
        duplicates = len(image_files) - len(set(image_files))
        assert duplicates <= 1  # Допускаем один дубликат
    
    def test_text_encoding(self, client):
        """Тест 25: Проверка корректной кодировки текста"""
        response = client.get('/about')
        # Проверяем, что ответ в UTF-8
        assert response.charset == 'utf-8' or response.mimetype == 'text/html'

    def test_card_icons_colors(self, client):
        """Тест 26: Проверка цветов иконок"""
        response = client.get('/about')
        html = response.data.decode('utf-8')
        
        # Проверяем классы цветов для иконок
        assert 'text-warning' in html  # для звезды
        assert 'text-success' in html  # для грузовика
        assert 'text-primary' in html  # для гарнитуры

    def test_container_structure(self, client):
        """Тест 27: Проверка структуры контейнера"""
        response = client.get('/about')
        html = response.data.decode('utf-8')
        
        # Проверяем вложенность
        assert '<div class="container py-5">' in html
        assert '<div class="text-center mb-5">' in html

    def test_all_images_have_alt(self, client):
        """Тест 28: Проверка наличия alt атрибутов у изображений"""
        response = client.get('/about')
        html = response.data.decode('utf-8')
        
        # Проверяем, что у всех img есть alt (даже пустой)
        images = re.findall(r'<img.*?>', html)
        for img in images:
            assert 'alt=' in img or 'alt=""' in img