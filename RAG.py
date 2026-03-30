import os
from typing import List, Dict
from dotenv import load_dotenv
import google.generativeai as genai
import PyPDF2

# ChromaDB и transformers - опционально (могут отсутствовать на Railway)
try:
    import chromadb
    from chromadb.config import Settings
    from transformers import AutoTokenizer, AutoModel
    import torch
    CHROMADB_ENABLED = True
    print("✅ ChromaDB и transformers загружены")
except ImportError as e:
    print(f"⚠️ ChromaDB/transformers не загружены: {e}")
    CHROMADB_ENABLED = False

load_dotenv()

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
genai.configure(api_key=GOOGLE_API_KEY)
model = genai.GenerativeModel('gemini-2.5-flash')

# Глобальная переменная для хранения функции получения данных из БД
get_products_from_db = None

def set_db_products_function(func):
    """Устанавливает функцию для получения товаров из БД"""
    global get_products_from_db
    get_products_from_db = func

# Инициализация эмбеддингов только если ChromaDB доступен
if CHROMADB_ENABLED:
    client_chroma = chromadb.Client(Settings(anonymized_telemetry=False))
    tokenizer = AutoTokenizer.from_pretrained("sentence-transformers/all-MiniLM-L6-v2")
    embedding_model = AutoModel.from_pretrained("sentence-transformers/all-MiniLM-L6-v2")
else:
    client_chroma = None
    tokenizer = None
    embedding_model = None

def get_embedding(text: str):
    if not CHROMADB_ENABLED or tokenizer is None or embedding_model is None:
        return None
    inputs = tokenizer(text, return_tensors="pt", padding=True, truncation=True, max_length=512)
    with torch.no_grad():
        outputs = embedding_model(**inputs)
        embeddings = outputs.last_hidden_state.mean(dim=1).numpy()
    return embeddings[0]

def chunk_text(text: str, chunk_size: int = 200, overlap: int = 20) -> List[str]:
    words = text.split()
    chunks = []
    i = 0
    while i < len(words):
        end = min(i + chunk_size, len(words))
        chunk = " ".join(words[i:end])
        chunks.append(chunk)
        i += end - overlap
    return chunks

def load_pdf(path: str) -> str:
    text = ""
    with open(path, 'rb') as f:
        pdf_reader = PyPDF2.PdfReader(f)
        for page in pdf_reader.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n"
    return text

def load_document(path: str) -> str:
    if path.lower().endswith('.pdf'):
        return load_pdf(path)
    with open(path, 'r', encoding='utf-8') as f:
        return f.read()

def insert_chunks(chunks: List[str], collection_name: str = "rag_chunks"):
    if not CHROMADB_ENABLED:
        print("⚠️ ChromaDB не доступен, пропуск индексации")
        return False
    collection = client_chroma.get_or_create_collection(name=collection_name)
    embeddings = [get_embedding(chunk) for chunk in chunks]
    collection.add(
        documents=chunks,
        embeddings=embeddings,
        ids=[f"chunk_{i}" for i in range(len(chunks))]
    )
    return True

def search_chunks(query: str, collection_name: str = "rag_chunks", top_k: int = 5) -> List[str]:
    if not CHROMADB_ENABLED:
        return []
    collection = client_chroma.get_or_create_collection(name=collection_name)
    query_embedding = get_embedding(query)
    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=top_k
    )
    return results['documents'][0] if results['documents'] else []

def get_products_context(query: str) -> str:
    """Получает контекст из БД товаров на основе запроса"""
    global get_products_from_db
    if get_products_from_db is None:
        return ""
    
    try:
        products = get_products_from_db(query)
        if not products:
            return ""
        
        context_parts = []
        for p in products[:10]:  # Берем топ-10 товаров
            context_parts.append(
                f"Товар: {p['name']}, Категория: {p['category']}, "
                f"Цена: {p['price']}₽, Описание: {p['description']}"
            )
        return "\n".join(context_parts)
    except Exception as e:
        print(f"Ошибка получения товаров из БД: {e}")
        return ""

def rag_query(user_query: str, history: List[Dict], collection_name: str = "rag_chunks") -> str:
    # Поиск в ChromaDB (если доступен)
    relevant_chunks = search_chunks(user_query, collection_name) if CHROMADB_ENABLED else []
    
    # Поиск товаров в БД
    db_context = get_products_context(user_query)

    # Объединяем контексты
    contexts = []
    if db_context:
        contexts.append(f"Товары из базы данных магазина:\n{db_context}")
    if relevant_chunks:
        contexts.append(f"Информация из документов:\n" + "\n\n".join(relevant_chunks))

    context = "\n\n".join(contexts)

    if context.strip():
        full_prompt = f"""На основе следующего контекста: {context}\n\nОтветь на вопрос: {user_query}.
        Отвечай на русском языке и используй информацию из контекста, и не только, если что-то отсутствует, то бери из открытых источников,
        так же ты эксперт-рыболов в рыболовном магазине и помогаешь людям подбирать снасти и комплектующие для рыбалки.
        Если в контексте есть товары из БД, рекомендуй их в первую очередь."""
        response = model.generate_content(full_prompt)
        return response.text if response.text else f"Найденная информация:\n{relevant_chunks[0] if relevant_chunks else 'Информация из БД доступна'}"
    else:
        response = model.generate_content(f"Ответь на вопрос: {user_query}. Отвечай на русском языке.")
        return response.text if response.text else "Извините, я не могу ответить на этот вопрос."

def add_document_to_rag(file_path: str):
    if not os.path.exists(file_path):
        print(f"Файл {file_path} не найден.")
        return False

    file_type = "PDF" if file_path.lower().endswith('.pdf') else "текстовый"
    print(f"Загрузка {file_type} документа: {file_path}")

    doc_text = load_document(file_path)
    chunks = chunk_text(doc_text)

    print(f"Разделение на {len(chunks)} чанков...")
    insert_chunks(chunks)

    print(f"Документ {file_path} успешно добавлен.")
    return True

def main():
    print("Загрузка модели эмбеддингов...")
    global embedding_model, tokenizer

    if os.path.exists("Fishing.txt"):
        print("Загрузка и индексация начального документа...")
        doc_text = load_document("Fishing.txt")
        chunks = chunk_text(doc_text)
        insert_chunks(chunks)
        print(f"Индексация завершена. Обработано {len(chunks)} чанков.")

    history = []

    while True:
        user_input = input("\nВы: ")
        if user_input.lower() == 'exit':
            break

        if user_input.lower().startswith('add_file '):
            file_path = user_input[9:].strip()
            add_document_to_rag(file_path)
            continue

        response = rag_query(user_input, history)
        print(f"\nБот: {response}")

        history.append({"role": "user", "content": user_input})
        history.append({"role": "assistant", "content": response})

if __name__ == "__main__":
    main()
