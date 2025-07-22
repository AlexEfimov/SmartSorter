from pathlib import Path
from .config import CATEGORIES, SUPPORTED_FORMATS
from .extractor import TextExtractor
from .categorizer import Categorizer
import os
import time
import shutil
import logging

class SmartSorter:
    def __init__(self, src_dir: Path, tgt_dir: Path, model: str):
        self.src_dir = src_dir
        self.tgt_dir = tgt_dir
        self.model = model
        self.extractor = TextExtractor()
        self.categorizer = Categorizer(model, CATEGORIES)
        print(f"SmartSorter initialized with:")
        print(f"  Source: {self.src_dir}")
        print(f"  Target: {self.tgt_dir}")
        print(f"  Model: {self.model}")

    def sort(self, window=None):
        """
        Analyzes files and returns a sorting plan.
        Does not move any files.
        Returns: A list of tuples, where each tuple is (source_path, destination_path).
        """
        self._update_progress(window, msg="Анализ файлов для сортировки...", log_only=True)
        
        # 1. Создаем папки для категорий
        for category_name in CATEGORIES.values():
            (self.tgt_dir / category_name).mkdir(parents=True, exist_ok=True)

        # 2. Получаем список файлов для сортировки
        files_to_sort = [
            f for f in self.src_dir.glob("**/*")
            if f.is_file() and f.suffix.lower() in SUPPORTED_FORMATS
        ]
        total_files = len(files_to_sort)
        self._update_progress(window, total=total_files, msg=f"Найдено {total_files} файлов для сортировки.", log_only=True)

        sorting_plan = []

        # 3. Основной цикл анализа
        for i, file_path in enumerate(files_to_sort):
            msg = f"Анализ: {file_path.name}"
            self._update_progress(window, done=i, total=total_files, msg=msg)

            text = self.extractor.extract(file_path)
            
            if not text or not text.strip():
                category_name = "Прочее"
                msg = f"Не удалось извлечь текст из {file_path.name}. Будет перемещен в 'Прочее'."
            else:
                category_name = self.categorizer.classify(text)
                msg = f"'{file_path.name}' классифицирован как '{category_name}'."

            target_folder_name = CATEGORIES.get(category_name, "Other")
            target_path = self.tgt_dir / target_folder_name
            
            sorting_plan.append((str(file_path), str(target_path)))
            
            self._update_progress(window, done=i + 1, total=total_files, msg=msg)
        
        self._update_progress(window, msg="Анализ завершен. План сортировки готов.", log_only=True)
        return sorting_plan

    def apply_sort(self, sorting_plan, window=None):
        """
        Applies a sorting plan by moving files.
        """
        total_files = len(sorting_plan)
        self._update_progress(window, total=total_files, msg="Применение плана сортировки...", log_only=True)
        
        for i, (src, dst_folder) in enumerate(sorting_plan):
            src_path = Path(src)
            msg = f"Перемещение '{src_path.name}' в '{Path(dst_folder).name}'"
            self._update_progress(window, done=i, total=total_files, msg=msg)
            
            try:
                shutil.move(src, dst_folder)
            except Exception as e:
                msg = f"Ошибка при перемещении {src_path.name}: {e}"
                logging.error(msg)

            self._update_progress(window, done=i + 1, total=total_files, msg=msg)

        self._update_progress(window, msg="Все файлы успешно перемещены!", log_only=True)

    def _update_progress(self, window, done=0, total=100, msg="", log_only=False):
        """Отправляет событие обновления прогресса в GUI."""
        if window:
            if log_only:
                window.write_event_value('-PROGRESS-', {'done': -1, 'total': -1, 'msg': msg})
            else:
                window.write_event_value('-PROGRESS-', {'done': done, 'total': total, 'msg': msg})

def main():
    """
    Main function for CLI or testing.
    """
    # This can be used to test the SmartSorter class
    # For example:
    # sorter = SmartSorter(Path("input"), Path("output"), "default_model")
    # sorter.sort()
    print("This is the main function in smart_sorter.main.")
    print("It can be used for CLI or testing purposes.")


if __name__ == "__main__":
    main()
