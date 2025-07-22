# main.py — CLI-интерфейс для SmartSorter

import sys
import os
from pathlib import Path

# Добавляем путь к проекту SmartSorter в sys.path
# Это необходимо, чтобы Python мог найти модуль smart_sorter
project_root = Path(__file__).parent
smart_sorter_path = project_root / 'SmartSorter'
if str(smart_sorter_path) not in sys.path:
    sys.path.insert(0, str(smart_sorter_path))

import argparse

from gui import GUI
from smart_sorter.main import SmartSorter

def main():
    """
    Главная функция для запуска CLI или GUI.
    """
    parser = argparse.ArgumentParser(description="SmartSorter: AI-powered file sorter.")
    
    # Добавляем аргумент для выбора режима
    parser.add_argument(
        'mode',
        nargs='?',
        default='gui',
        choices=['gui', 'cli'],
        help="Режим работы: 'gui' для графического интерфейса (по умолчанию) или 'cli' для командной строки."
    )
    
    # Аргументы для CLI
    parser.add_argument(
        '--src',
        type=Path,
        help="Путь к исходной папке с файлами (для режима cli)."
    )
    parser.add_argument(
        '--tgt',
        type=Path,
        help="Путь к папке для сохранения результатов (для режима cli)."
    )
    parser.add_argument(
        '--model',
        type=str,
        help="Имя модели Ollama для использования (для режима cli)."
    )

    args = parser.parse_args()

    if args.mode == 'gui':
        print("Запуск в режиме GUI...")
        gui = GUI()
        gui.run()
    elif args.mode == 'cli':
        if not args.src or not args.tgt:
            parser.error("--src и --tgt обязательны для режима cli.")
        
        print(f"Запуск в режиме CLI...")
        print(f"Исходная папка: {args.src}")
        print(f"Папка назначения: {args.tgt}")
        if args.model:
            print(f"Модель: {args.model}")
        
        sorter = SmartSorter(args.src, args.tgt, args.model)
        sorter.sort()

if __name__ == "__main__":
    main() 