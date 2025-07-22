# gui.py — графический интерфейс для SmartSorter

import PySimpleGUI as sg
from pathlib import Path
import threading
import subprocess
import os
import signal
import time
import json

from smart_sorter.main import SmartSorter
from smart_sorter.config import CATEGORIES, DEFAULT_MODEL

OLLAMA_BIN = "/opt/homebrew/bin/ollama"
OLLAMA_PORT = 11434
OLLAMA_LOG = Path("ollama_log.txt")
MODEL_CFG = Path("last_llm_model.json")

def is_ollama_running():
    try:
        result = subprocess.run(
            ["lsof", "-Pi", f":{OLLAMA_PORT}", "-sTCP:LISTEN", "-t"],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
        )
        return result.stdout.strip().splitlines()
    except Exception:
        return []

def start_ollama(log_callback):
    """Пытается запустить сервер Ollama, если он еще не запущен."""
    if not Path(OLLAMA_BIN).exists():
        log_callback(f"Не удалось запустить Ollama: исполняемый файл не найден по пути {OLLAMA_BIN}")
        return None
    if is_ollama_running():
        # Сервер уже работает, ничего не делаем
        return None
    
    log_callback("Сервер Ollama не запущен. Попытка запуска...")
    env = os.environ.copy()
    env["PATH"] += ":/opt/homebrew/bin"
    try:
        proc = subprocess.Popen([OLLAMA_BIN, "serve"], preexec_fn=os.setsid, env=env)
        log_callback("Команда на запуск сервера Ollama отправлена.")
        return proc
    except Exception as e:
        log_callback(f"Ошибка при запуске сервера Ollama: {e}")
        return None

def get_ollama_models(log_callback):
    """
    Получает список моделей из Ollama.
    Возвращает кортеж: (список_моделей, сообщение_об_ошибке_или_None)
    """
    if not Path(OLLAMA_BIN).exists():
        msg = f"Ollama не найдена по пути: {OLLAMA_BIN}"
        log_callback(msg)
        return [], msg

    try:
        result = subprocess.run(
            [OLLAMA_BIN, "list"], capture_output=True, text=True, timeout=10
        )
        if result.returncode != 0:
            msg = f"Ошибка при вызове 'ollama list': {result.stderr.strip()}"
            log_callback(msg)
            return [], msg

        lines = result.stdout.strip().splitlines()[1:]
        models = [line.split()[0] for line in lines if line.strip()]
        
        if not models:
            msg = "Модели Ollama не найдены. Убедитесь, что они установлены."
            log_callback(msg)
            return [], msg
            
        return models, None
    except FileNotFoundError:
        msg = f"Ollama не найдена. Проверьте путь: {OLLAMA_BIN}"
        log_callback(msg)
        return [], msg
    except Exception as e:
        msg = f"Не удалось получить модели Ollama: {e}"
        log_callback(msg)
        return [], msg

def load_last_model(models):
    if MODEL_CFG.exists():
        with open(MODEL_CFG, "r", encoding="utf-8") as f:
            name = json.load(f).get("last_model")
            if name in models:
                return name
    if models:
        return models[0]
    return DEFAULT_MODEL

def save_last_model(name):
    with open(MODEL_CFG, "w", encoding="utf-8") as f:
        json.dump({"last_model": name}, f)


def human_readable_size(size, decimal_places=2):
    """Конвертирует байты в человекочитаемый формат (KB, MB, GB)."""
    if size is None:
        return ""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size < 1024.0:
            break
        size /= 1024.0
    return f"{size:.{decimal_places}f} {unit}"

_EXCLUDED_KEY = "Исключить из сортировки"
_EXCLUDED_DISPLAY_TEXT = "--- ИСКЛЮЧЕНО ---"


def create_preview_window(sorting_plan):
    """Создает окно предпросмотра и редактирования плана сортировки с возможностью сортировки и исключения файлов."""
    
    original_plan = list(sorting_plan)
    header = ['Файл', 'Тип', 'Размер', 'Категория']
    category_keys = list(CATEGORIES.keys())
    right_click_menu_options = category_keys + ['---', _EXCLUDED_KEY] 

    # --- 1. Подготовка данных ---
    # `rich_data` - это наш основной источник данных. Все изменения сначала вносятся сюда.
    rich_data = []
    for i, (src, dst_folder) in enumerate(original_plan):
        src_path = Path(src)
        dst_path = Path(dst_folder)
        category_key = next((k for k, v in CATEGORIES.items() if v == dst_path.name), "Прочее")
        try:
            file_size_bytes = src_path.stat().st_size if src_path.is_file() else 0
        except (FileNotFoundError, PermissionError):
            file_size_bytes = 0
        
        rich_data.append({
            "name": src_path.name,
            "type": src_path.suffix.lower(),
            "size": file_size_bytes,
            "category": category_key,
            "last_known_category": category_key,
            "original_index": i,
            "is_excluded": False,
            "is_changed": False
        })

    def get_display_data_from_rich(data):
        """Преобразует `rich_data` в простой список списков для отображения в таблице."""
        return [[d["name"], d["type"], human_readable_size(d["size"]), d["category"]] for d in data]

    # --- 2. Определение макета окна ---
    layout = [
        [sg.Text("План сортировки:", font=("Helvetica", 16))],
        [sg.Text("Кликните на заголовок для сортировки. Кликните правой кнопкой мыши на файл для действий.")],
        [sg.Table(values=get_display_data_from_rich(rich_data), headings=header,
                  auto_size_columns=False, col_widths=[40, 10, 15, 20],
                  display_row_numbers=True, justification='left',
                  num_rows=min(20, len(rich_data)), key='-TABLE-',
                  row_height=25, enable_events=True,
                  enable_click_events=True,
                  right_click_menu=['', right_click_menu_options],
                  right_click_selects=True,
                  select_mode=sg.TABLE_SELECT_MODE_BROWSE)],
        [sg.Button("Применить"), sg.Button("Отмена")]
    ]
    
    window = sg.Window("Предпросмотр и редактирование", layout, modal=True, finalize=True)
    sort_state = {'col': -1, 'asc': True}

    def update_table_display():
        """Централизованная функция для обновления таблицы и цветов строк."""
        display_data = get_display_data_from_rich(rich_data)
        row_colors = []
        for i, item in enumerate(rich_data):
            if item["is_excluded"]:
                row_colors.append((i, '#cccccc'))  # Серый для исключенных
            elif item["is_changed"]:
                row_colors.append((i, 'lightblue')) # Голубой для измененных
        window['-TABLE-'].update(values=display_data, row_colors=row_colors)

    # --- 3. Основной цикл событий ---
    while True:
        event, values = window.read()

        if event in (sg.WINDOW_CLOSED, "Отмена"):
            final_plan = None
            break
        
        # --- Обработка клика по заголовку (Сортировка) ---
        if isinstance(event, tuple) and event[0] == '-TABLE-' and event[1] == '+CLICKED+':
            row, col = event[2]
            if row == -1 and col is not None: 
                col_name_map = {0: "name", 1: "type", 2: "size", 3: "category"}
                key_to_sort = col_name_map.get(col)
                if key_to_sort:
                    if sort_state['col'] == col:
                        sort_state['asc'] = not sort_state['asc']
                    else:
                        sort_state['col'] = col
                        sort_state['asc'] = True
                    
                    # --- Улучшенная функция для ключа сортировки ---
                    def sort_key_func(item):
                        val = item.get(key_to_sort)
                        # Для строк используем регистронезависимую сортировку
                        if isinstance(val, str):
                            return val.lower()
                        # Для чисел и других типов - оставляем как есть
                        return val

                    rich_data.sort(key=sort_key_func, reverse=not sort_state['asc'])
                    update_table_display() # Немедленно обновляем таблицу
        
        # --- Обработка действий из контекстного меню ---
        elif event in right_click_menu_options:
            if values['-TABLE-']:
                # Индекс `data_idx` теперь всегда правильный, т.к. view и model синхронизированы
                data_idx = values['-TABLE-'][0]
                rich_item = rich_data[data_idx]
                
                if event == _EXCLUDED_KEY:
                    rich_item["is_excluded"] = not rich_item["is_excluded"]
                    if rich_item["is_excluded"]:
                        rich_item["category"] = _EXCLUDED_DISPLAY_TEXT
                    else: # Возвращаем последнюю известную категорию
                        rich_item["category"] = rich_item["last_known_category"]

                elif event in category_keys: # Если выбрана новая категория
                    rich_item["category"] = event
                    rich_item["last_known_category"] = event # Запоминаем ее
                    rich_item["is_excluded"] = False # Снимаем флаг исключения
                    rich_item["is_changed"] = True   # Помечаем как измененную
                
                update_table_display() # Немедленно обновляем таблицу

        # --- Обработка нажатия "Применить" ---
        elif event == "Применить":
            final_plan = []
            for item in rich_data:
                if item["is_excluded"]:
                    continue # Пропускаем исключенные файлы
                original_idx = item["original_index"]
                original_src, original_dst = original_plan[original_idx]
                new_dst_folder_name = CATEGORIES.get(item["category"], "Other")
                new_dst_path = Path(original_dst).parent / new_dst_folder_name
                final_plan.append((original_src, str(new_dst_path)))
            break

    window.close()
    return final_plan


sg.theme('SystemDefault')

class GUI:
    def __init__(self):
        self.layout = [
            [sg.Text('Папка с исходными файлами:'), sg.Input(key='src'), sg.FolderBrowse()],
            [sg.Text('Папка для сохранения результатов:'), sg.Input(key='tgt'), sg.FolderBrowse()],
            [sg.Text('LLM-модель:'), sg.Combo(["Загрузка..."], key='model', readonly=True)],
            [sg.Button('Анализ'), sg.Button('Обновить модели'), sg.Button('Выход')],
            [sg.ProgressBar(100, orientation='h', size=(40, 15), key='bar', visible=False)],
            [sg.Multiline('', size=(80, 20), key='log', autoscroll=True, disabled=True)]
        ]
        self.window = sg.Window('SmartSorter GUI', self.layout, finalize=True)
        self.model_elem = self.window['model']
        self.log_elem = self.window['log']
        self.progress = self.window['bar']
        self.ollama_proc = None
        self.sorting_plan = None

    def _load_models(self):
        models, error_msg = get_ollama_models(self._update_log)
        if error_msg:
            # Если есть ошибка, отображаем ее в выпадающем списке
            self.window.write_event_value('-MODELS-', ([error_msg], error_msg))
        else:
            selected = load_last_model(models)
            self.window.write_event_value('-MODELS-', (models, selected))

    def _update_log(self, msg):
        self.log_elem.update(f"[{time.strftime('%H:%M:%S')}] {msg}\n", append=True)

    def run(self):
        self._update_log("Проверка состояния Ollama...")
        # Пытаемся запустить сервер Ollama, если он не работает
        proc = start_ollama(self._update_log)
        if proc:
            self.ollama_proc = proc
            self._update_log("Ожидание готовности сервера (5 секунд)...")
            time.sleep(5) # Даем серверу время на запуск
        elif is_ollama_running():
            self._update_log("Сервер Ollama уже запущен.")

        threading.Thread(target=self._load_models, daemon=True).start()

        while True:
            event, values = self.window.read(timeout=100)
            if event in (sg.WINDOW_CLOSED, 'Выход'):
                break
            if event == '-MODELS-':
                models, selected = values['-MODELS-']
                self.model_elem.update(values=models, value=selected, readonly=len(models) <= 1)
            if event == 'Обновить модели':
                self.model_elem.update(values=["Загрузка..."], value="Загрузка...", readonly=True)
                self._update_log("Обновление списка моделей...")
                threading.Thread(target=self._load_models, daemon=True).start()
            if event == 'Анализ':
                src, tgt, model = values['src'], values['tgt'], values['model']
                if not src or not tgt or not model:
                    sg.popup_error("Заполните все поля!")
                    continue
                save_last_model(model)
                
                # Проверяем и запускаем Ollama, если это необходимо
                if not is_ollama_running():
                    proc = start_ollama(self._update_log)
                    if proc:
                        self.ollama_proc = proc

                def run_analysis():
                    sorter = SmartSorter(Path(src), Path(tgt), model)
                    self.sorting_plan = sorter.sort(self.window)
                    self.window.write_event_value('-ANALYSIS_DONE-', '')
                
                threading.Thread(target=run_analysis, daemon=True).start()
                self.progress.update(0, visible=True)
                self.log_elem.update("")

            if event == '-ANALYSIS_DONE-':
                self.progress.update(0, visible=False)
                if not self.sorting_plan:
                    sg.popup_error("Анализ не вернул план сортировки. Возможно, не найдено файлов.")
                    continue

                # Показываем окно предпросмотра и получаем результат
                final_plan = create_preview_window(self.sorting_plan)
                
                if final_plan:
                    self._update_log("Применение отсортированного плана...")
                    # Передаем final_plan в apply_sort
                    src, tgt, model = values['src'], values['tgt'], values['model']
                    sorter = SmartSorter(Path(src), Path(tgt), model)
                    
                    def run_apply():
                        sorter.apply_sort(final_plan, self.window)
                        self.window.write_event_value('-APPLY_DONE-', '')
                    
                    threading.Thread(target=run_apply, daemon=True).start()
                    self.progress.update(0, visible=True)

            if event == '-APPLY_DONE-':
                sg.popup_ok("Сортировка успешно применена!")
                self.progress.update(0, visible=False)


            if event == '-PROGRESS-':
                v = values['-PROGRESS-']
                # Если пришли данные только для лога, обновляем только его
                if v['done'] == -1 and v['total'] == -1:
                    self._update_log(v['msg'])
                else:
                    p = int(v['done'] / v['total'] * 100) if v['total'] else 0
                    self.progress.update(p)
                    self._update_log(v['msg'])

            if event == '-DONE-':
                sg.popup_ok("Сортировка завершена!")
                self.progress.update(0, visible=False)

        self.window.close()
        if self.ollama_proc:
            os.killpg(os.getpgid(self.ollama_proc.pid), signal.SIGTERM)

if __name__ == '__main__':
    gui = GUI()
    gui.run()
