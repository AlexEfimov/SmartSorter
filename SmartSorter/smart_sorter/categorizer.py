# categorizer.py — Классификация текста через LLM (Ollama)

import requests
import logging
from typing import Dict


class Categorizer:
    def __init__(self, model: str, categories: Dict[str, str]):
        self.model = model
        self.categories = categories
        self.categories_text = ", ".join(f"'{k}'" for k in categories.keys())

    def classify(self, text: str) -> str:
        prompt = (
            "Твоя задача - классифицировать документ на основе его содержания. "
            "Проанализируй следующий текст и определи, к какой из этих категорий он относится: "
            f"{self.categories_text}. "
            "В качестве ответа верни ТОЛЬКО ОДНО название категории из предоставленного списка. "
            "Например, если документ - это посадочный талон, верни 'Проездные документы'.\n\n"
            "--- Текст документа для анализа ---\n"
            f"{text[:4000]}\n"
            "--- Конец текста ---\n\n"
            "Категория:"
        )
        try:
            response = requests.post(
                "http://localhost:11434/api/chat",
                json={
                    "model": self.model,
                    "messages": [{"role": "user", "content": prompt}],
                    "stream": False,
                    "options": {
                        "temperature": 0.0
                    }
                },
                timeout=60  # Увеличиваем таймаут до 60 секунд
            )
            response.raise_for_status() # Проверка на ошибки HTTP (4xx, 5xx)
            content = response.json().get("message", {}).get("content", "").strip().replace("'", "")

        except requests.exceptions.RequestException as e:
            logging.error(f"Ошибка сети при обращении к LLM: {e}")
            return "Прочее"
        except Exception as e:
            logging.error(f"Неизвестная ошибка LLM при классификации: {e}")
            return "Прочее"

        # Некоторые модели возвращают свои "мысли" в теге <think>.
        # Мы должны извлечь только итоговый ответ после этого тега.
        think_end_tag = "</think>"
        if think_end_tag in content:
            content = content.split(think_end_tag, 1)[-1]
            
        # Ищем наиболее вероятную категорию в очищенном ответе модели
        content_lower = content.lower().strip().replace("'", "").replace('"',"")

        # 1. Сначала ищем точное совпадение
        for key in self.categories:
            if key.lower() == content_lower:
                return key

        # 2. Если точного совпадения нет, ищем, какая из категорий содержится в ответе.
        # Это помогает, если модель отвечает "Категория: Книги" вместо просто "Книги".
        found_categories = []
        for key in self.categories:
            if key.lower() in content_lower:
                found_categories.append(key)
        
        if len(found_categories) == 1:
            logging.info(f"Найдено неточное совпадение для ответа '{content}', используется категория '{found_categories[0]}'.")
            return found_categories[0]
        
        if len(found_categories) > 1:
            # Если найдено несколько, выберем самую длинную (наиболее конкретную)
            best_match = max(found_categories, key=len)
            logging.info(f"Найдено несколько категорий в ответе '{content}': {found_categories}. Выбрана самая длинная: '{best_match}'.")
            return best_match

        logging.warning(f"Модель вернула неожиданный ответ: '{content}'. Используется категория 'Прочее'.")
        return "Прочее"
