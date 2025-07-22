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
from smart_sorter.config import DEFAULT_MODEL

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

sg.theme('SystemDefault')

class GUI:
    def __init__(self):
        self.layout = [
            [sg.Text('Папка с исходными файлами:'), sg.Input(key='src'), sg.FolderBrowse()],
            [sg.Text('Папка для сохранения результатов:'), sg.Input(key='tgt'), sg.FolderBrowse()],
            [sg.Text('LLM-модель:'), sg.Combo(["Загрузка..."], key='model', readonly=True)],
            [sg.Button('Запуск'), sg.Button('Обновить модели'), sg.Button('Выход')],
            [sg.ProgressBar(100, orientation='h', size=(40, 15), key='bar', visible=False)],
            [sg.Multiline('', size=(80, 20), key='log', autoscroll=True, disabled=True)]
        ]
        self.window = sg.Window('SmartSorter GUI', self.layout, finalize=True)
        self.model_elem = self.window['model']
        self.log_elem = self.window['log']
        self.progress = self.window['bar']
        self.ollama_proc = None

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
            if event == 'Запуск':
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

                def run_sort():
                    sorter = SmartSorter(Path(src), Path(tgt), model)
                    sorter.sort(self.window)
                    self.window.write_event_value('-DONE-', '')
                threading.Thread(target=run_sort, daemon=True).start()
                self.progress.update(0, visible=True)
                self.log_elem.update("")

            if event == '-PROGRESS-':
                v = values['-PROGRESS-']
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
