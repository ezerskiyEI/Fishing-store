# 🚀 Деплой на Railway (0.5 ГБ памяти)

## 📋 Подготовка

### 1. Получи DATABASE_URL из своей Railway PostgreSQL

1. Зайди в [Railway Dashboard](https://railway.app/)
2. Выбери свой проект с PostgreSQL
3. Нажми на базу данных → **Variables**
4. Скопируй `DATABASE_URL` (выглядит как `postgresql://postgres:...@host.railway.app:port/database`)

### 2. Получи Google API Key (для RAG)

1. Зайди на [Google AI Studio](https://aistudio.google.com/app/apikey)
2. Создай новый API key
3. Скопируй его

---

## 🔧 Шаг 1: Push в Git

```bash
# Если ещё не инициализирован git
git init
git add .
git commit -m "Initial commit for Railway"

# Создай репозиторий на GitHub и запушь
git remote add origin https://github.com/yourusername/fishing-store.git
git branch -M main
git push -u origin main
```

---

## 🔧 Шаг 2: Подключи Railway к GitHub

1. Зайди на [Railway](https://railway.app/)
2. Нажми **New Project**
3. Выбери **Deploy from GitHub repo**
4. Выбери свой репозиторий `fishing-store`

---

## 🔧 Шаг 3: Настрой переменные окружения

В Railway Dashboard перейди в **Variables** и добавь:

| Переменная | Значение |
|------------|----------|
| `DATABASE_URL` | Твой URL от PostgreSQL (из шага 1) |
| `TELEGRAM_BOT_TOKEN` | `8478250303:AAGO88C82UCxrZ8dJjJEDogbL6hKjPy4Izs` |
| `GOOGLE_API_KEY` | Твой ключ от Google AI |
| `CLOUDINARY_CLOUD_NAME` | Твой cloud name из `db.env` |
| `CLOUDINARY_API_KEY` | Твой key из `db.env` |
| `CLOUDINARY_API_SECRET` | Твой secret из `db.env` |
| `SECRET_KEY` | Любая случайная строка (например `fishing_key_2026`) |
| `WEBAPP_URL` | Оставь пустым (Railway сам подставит) |
| `PYTHONMALLOC` | `malloc` (оптимизация памяти) |
| `MALLOC_MMAP_THRESHOLD_` | `32768` (оптимизация памяти) |

---

## 🔧 Шаг 4: Настрой Deploy

Railway автоматически определит `railway.json` и `Dockerfile`.

**Проверь настройки:**
- **Builder**: Dockerfile
- **Start Command**: `gunicorn --bind 0.0.0.0:$PORT --workers 2 --threads 2 --timeout 30 app:app`

---

## 🔧 Шаг 5: Деплой

1. Нажми **Deploy**
2. Дождись сборки (около 3-5 минут)
3. Railway выдаст URL вида `https://your-project.railway.app`

---

## 🔧 Шаг 6: Инициализация БД

После первого деплоя нужно создать таблицы:

### Вариант A: Через Railway CLI

```bash
# Установи CLI
npm install -g @railway/cli

# Логин
railway login

# Подключись к проекту
railway link

# Запусти миграции
railway run python -c "from app import app, db; app.app_context().push(); db.create_all(); print('✅ БД создана')"
```

### Вариант B: Автоматически при старте

В `app.py` уже есть код для автоматического создания таблиц при старте.

---

## 🔧 Шаг 7: Создай админа

Открой в браузере:
```
https://your-project.railway.app/create_admin
```

Или через Railway CLI:
```bash
railway run python -c "from app import app, db, generate_password_hash, User; app.app_context().push(); admin = User(username='admin', email='beztele153@gmail.com', password=generate_password_hash('admin123'), is_admin=True); db.session.add(admin); db.session.commit(); print('✅ Админ создан')"
```

---

## ⚠️ Оптимизация для 0.5 ГБ памяти

### Что уже сделано:

1. **Убраны тяжёлые зависимости** из `requirements.txt`:
   - `chromadb` (занимает ~200 МБ)
   - `transformers`, `torch`, `sentence-transformers` (занимают ~1 ГБ)
   
2. **Добавлен Gunicorn** с 2 воркерами и 2 потоками (экономит память)

3. **Оптимизирован Dockerfile**:
   - `PYTHONDONTWRITEBYTECODE=1` — не создаёт `.pyc` файлы
   - `PIP_NO_CACHE_DIR=1` — не кэширует пакеты
   - `apt-get clean` — очищает кэш

4. **Добавлены переменные для malloc**:
   - `PYTHONMALLOC=malloc`
   - `MALLOC_MMAP_THRESHOLD_=32768`

### Если память всё равно заканчивается:

1. **Уменьши количество воркеров Gunicorn** в `railway.json`:
   ```json
   "startCommand": "gunicorn --bind 0.0.0.0:$PORT --workers 1 --threads 2 --timeout 30 app:app"
   ```

2. **Отключи Telegram-бота** (если не нужен):
   В `app.py` закомментируй запуск бота:
   ```python
   # bot_thread = threading.Thread(target=run_bot_safe, daemon=True)
   # bot_thread.start()
   ```

3. **Уменьши pool_size** в `app.config['SQLALCHEMY_ENGINE_OPTIONS']`:
   ```python
   "pool_size": 5,  # было 10
   "max_overflow": 10  # было 20
   ```

---

## 🧪 Проверка работы

1. Открой `https://your-project.railway.app`
2. Проверь главную страницу (лунный календарь, новости)
3. Зайди в каталог
4. Попробуй добавить товар в корзину
5. Зайди в админку (`/admin`) — логин: `admin`, пароль: `admin123`

---

## 🐛 Частые проблемы

### ❌ "Build failed" или "Container exited"

**Причина:** Нехватка памяти при сборке.

**Решение:**
```bash
# Локально собери образ и проверь
docker build -t fishing-store .
docker run -p 5000:5000 fishing-store
```

### ❌ "SSL SYSCALL error: EOF detected"

**Причина:** Обрыв соединения с БД.

**Решение:** Убедись, что в `app.py` есть настройки:
```python
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
    "pool_pre_ping": True,
    "pool_recycle": 300,
    ...
}
```

### ❌ "RAG не работает"

**Причина:** Отсутствует `GOOGLE_API_KEY` или тяжёлые библиотеки удалены.

**Решение:**
- Если нужен RAG — добавь зависимости обратно в `requirements.txt` (но будет больше памяти)
- Или используй только поиск по БД товаров

### ❌ "Память 100%"

**Причина:** Утечка памяти или тяжёлые запросы.

**Решение:**
1. Проверь логи в Railway Dashboard
2. Уменьши `pool_size` до 3-5
3. Отключи Telegram-бота
4. Используй Railway Pro план (больше памяти)

---

## 📊 Мониторинг

В Railway Dashboard смотри:
- **Metrics** — использование CPU и памяти
- **Logs** — логи приложения
- **Deployments** — история деплоев

---

## 🔄 Обновление проекта

```bash
# Внеси изменения локально
git add .
git commit -m "Update feature"
git push

# Railway автоматически пересоберёт проект
```

Или вручную в Railway Dashboard: **Deployments** → **Redeploy**

---

**Готово!** 🎣 Твой магазин на Railway!
