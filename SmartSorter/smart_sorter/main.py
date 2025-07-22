from pathlib import Path
from .config import CATEGORIES, SUPPORTED_FORMATS
from .extractor import TextExtractor
from .categorizer import Categorizer
import os
import time
import shutil

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
        Main sorting logic.
        """
        print("Sorting process started...")
        if window:
            self._update_progress(window, msg="Создание папок категорий...")

        # 1. Создаем папки для категорий
        for category_name in CATEGORIES.values():
            category_path = self.tgt_dir / category_name
            category_path.mkdir(parents=True, exist_ok=True)

        # 2. Получаем список файлов для сортировки
        files_to_sort = [
            f for f in self.src_dir.glob("**/*")
            if f.is_file() and f.suffix.lower() in SUPPORTED_FORMATS
        ]
        total_files = len(files_to_sort)
        print(f"Found {total_files} files to sort.")
        if window:
            self._update_progress(window, total=total_files, msg=f"Найдено {total_files} файлов для сортировки.")

        # 3. Основной цикл сортировки
        for i, file_path in enumerate(files_to_sort):
            msg = f"Обработка: {file_path.name}"
            print(msg)
            if window:
                self._update_progress(window, done=i, total=total_files, msg=msg)

            # 3.1 Извлечение текста
            text = self.extractor.extract(file_path)
            
            if not text or not text.strip():
                category_name = "Прочее"
                msg = f"Не удалось извлечь текст из {file_path.name}. Перемещен в 'Прочее'."
            else:
                # 3.2 Классификация
                category_name = self.categorizer.classify(text)
                msg = f"'{file_path.name}' классифицирован как '{category_name}'."

            print(msg)

            # 3.3 Перемещение файла
            target_folder_name = CATEGORIES.get(category_name, "Other")
            target_path = self.tgt_dir / target_folder_name
            shutil.move(str(file_path), str(target_path))
            
            if window:
                self._update_progress(
                    window,
                    done=i + 1,
                    total=total_files,
                    msg=msg
                )
        
        if window:
            self._update_progress(
                window,
                done=total_files,
                total=total_files,
                msg="Сортировка завершена!"
            )
        print("Sorting process finished.")

    def _update_progress(self, window, done=0, total=100, msg=""):
        """Отправляет событие обновления прогресса в GUI."""
        if window:
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
