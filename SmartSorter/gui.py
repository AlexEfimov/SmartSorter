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


def create_preview_window(sorting_plan):
    """Создает окно предпросмотра и редактирования плана сортировки."""
    
    header = ['Файл', 'Категория']
    original_plan = list(sorting_plan) 
    category_keys = list(CATEGORIES.keys())
    
    table_data = []
    for src, dst_folder in original_plan:
        src_path = Path(src)
        dst_name = Path(dst_folder).name
        category_key = next((k for k, v in CATEGORIES.items() if v == dst_name), "Прочее")
        table_data.append([src_path.name, category_key])

    layout = [
        [sg.Text("План сортировки:", font=("Helvetica", 16))],
        [sg.Text("Кликните правой кнопкой мыши на файл, чтобы изменить его категорию.")],
        [sg.Table(values=table_data, headings=header,
                  auto_size_columns=False, col_widths=[40, 20],
                  display_row_numbers=True, justification='left',
                  num_rows=min(15, len(table_data)), key='-TABLE-',
                  row_height=25, enable_events=True,
                  right_click_menu=['', category_keys], # Включаем контекстное меню
                  select_mode=sg.TABLE_SELECT_MODE_BROWSE)],
        [sg.Button("Применить"), sg.Button("Отмена")]
    ]
    
    window = sg.Window("Предпросмотр и редактирование", layout, modal=True, finalize=True)
    
    changed_rows = set()

    while True:
        event, values = window.read()

        if event in (sg.WINDOW_CLOSED, "Отмена"):
            final_plan = None
            break
        
        # Проверяем, является ли событие выбором из контекстного меню
        if event in category_keys:
            selected_row_indices = values['-TABLE-']
            if selected_row_indices:
                selected_row_index = selected_row_indices[0]
                new_category = event # Событие и есть имя категории
                
                # Обновляем данные в таблице
                table_data[selected_row_index][1] = new_category
                changed_rows.add(selected_row_index)
                
                # Обновляем GUI с подсветкой
                row_colors = [(i, 'lightblue') for i in changed_rows]
                window['-TABLE-'].update(values=table_data, row_colors=row_colors)
            else:
                # Такое может случиться, если меню было вызвано без выбора строки
                sg.popup("Не удалось определить выбранную строку. Кликните на строку левой кнопкой мыши, а затем правой.", keep_on_top=True)
        
        if event == "Применить":
            # Конвертируем отредактированные данные обратно в формат плана
            final_plan = []
            for i, row in enumerate(table_data):
                original_src_path, _ = original_plan[i]
                new_category_key = row[1]
                new_dst_folder_name = CATEGORIES.get(new_category_key, "Other")
                # Восстанавливаем полный путь к целевой папке
                original_tgt_path = Path(original_plan[i][1]).parent
                new_dst_path = original_tgt_path / new_dst_folder_name
                final_plan.append((original_src_path, str(new_dst_path)))
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
                self.sorting_plan = None


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
