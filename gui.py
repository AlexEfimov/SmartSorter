# gui.py — графический интерфейс для SmartSorter

import PySimpleGUI as sg
from pathlib import Path
import threading
import subprocess
import os
import signal
import time
import json
from typing import List, Optional, Tuple, Any

from smart_sorter.config import config
# Убираем импорт SmartSorter отсюда, чтобы избежать цикла

class OllamaManager:
    """Управляет запуском, остановкой и взаимодействием с сервером Ollama."""

    def __init__(self):
        self.proc: Optional[subprocess.Popen] = None

    def is_running(self) -> bool:
        """Проверяет, запущен ли процесс Ollama на нужном порту."""
        try:
            result = subprocess.run(
                ["lsof", "-Pi", f":{config.ollama_base_url.split(':')[-1]}", "-sTCP:LISTEN", "-t"],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True
            )
            return bool(result.stdout.strip())
        except (Exception, subprocess.CalledProcessError):
            return False

    def start(self) -> bool:
        """Запускает сервер Ollama, если он еще не запущен."""
        if self.is_running():
            return True
        
        env = os.environ.copy()
        env["PATH"] = f"{Path(config.ollama_executable_path).parent}:{env.get('PATH', '')}"
        
        try:
            self.proc = subprocess.Popen(
                [config.ollama_executable_path, "serve"],
                preexec_fn=os.setsid,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            # Дадим серверу время на запуск
            time.sleep(3)
            return self.is_running()
        except FileNotFoundError:
            sg.popup_error(f"Не найден исполняемый файл Ollama: {config.ollama_executable_path}")
            return False
        except Exception as e:
            sg.popup_error(f"Ошибка при запуске Ollama: {e}")
            return False

    def stop(self):
        """Останавливает процесс Ollama, если он был запущен этим менеджером."""
        if self.proc:
            os.killpg(os.getpgid(self.proc.pid), signal.SIGTERM)
            self.proc.wait()
            self.proc = None

    @staticmethod
    def get_models() -> List[str]:
        """Получает список доступных моделей Ollama."""
        try:
            result = subprocess.run(
                [config.ollama_executable_path, "list"],
                capture_output=True, text=True, timeout=10, check=True
            )
            lines = result.stdout.splitlines()[1:]
            return [line.split()[0] for line in lines if line.strip()] or [config.ollama_model]
        except Exception as e:
            sg.popup(f"Не удалось получить список моделей Ollama: {e}\n\nБудет использована модель по умолчанию.", title="Ошибка")
            return [config.ollama_model]

class GUI:
    """Основной класс графического интерфейса."""

    def __init__(self):
        self.ollama_manager = OllamaManager()
        self.model_cfg_path = Path("last_llm_model.json")
        self.window = self._create_window()

    def _create_window(self) -> sg.Window:
        """Создает и возвращает главное окно приложения."""
        sg.theme('SystemDefault')
        layout = [
            [sg.Text('Папка с исходными файлами:'), sg.Input(key='-SRC-'), sg.FolderBrowse()],
            [sg.Text('Папка для сохранения результатов:'), sg.Input(key='-TGT-'), sg.FolderBrowse()],
            [sg.Text('LLM-модель:'), sg.Combo([], key='-MODEL-', readonly=True, size=(30, 1))],
            [sg.Button('Запуск'), sg.Button('Обновить модели'), sg.Button('Выход')],
            [sg.ProgressBar(100, orientation='h', size=(40, 15), key='-BAR-', visible=False)],
            [sg.Multiline('', size=(80, 20), key='-LOG-', autoscroll=True, disabled=True, reroute_stdout=True, reroute_stderr=True)]
        ]
        return sg.Window('SmartSorter GUI', layout, finalize=True)

    def _load_models(self):
        """Загружает модели в фоновом потоке."""
        models = self.ollama_manager.get_models()
        selected_model = self._load_last_model(models)
        self.window.write_event_value('-MODELS-LOADED-', (models, selected_model))

    def _load_last_model(self, models: List[str]) -> str:
        """Загружает последнее использованное имя модели."""
        if self.model_cfg_path.exists():
            try:
                with open(self.model_cfg_path, "r", encoding="utf-8") as f:
                    name = json.load(f).get("last_model")
                    if name in models:
                        return name
            except (json.JSONDecodeError, IOError):
                pass
        return models[0] if models else config.ollama_model

    def _save_last_model(self, name: str):
        """Сохраняет последнее использованное имя модели."""
        try:
            with open(self.model_cfg_path, "w", encoding="utf-8") as f:
                json.dump({"last_model": name}, f)
        except IOError:
            pass

    def _run_sorting_thread(self, src: str, tgt: str, model: str):
        """Запускает процесс сортировки в отдельном потоке."""
        from smart_sorter.main import SmartSorter # Импортируем здесь
        try:
            sorter = SmartSorter(Path(src), Path(tgt), model)
            # Мы знаем, что window существует в этом контексте
            sorter.sort(self.window)  # type: ignore
        except Exception as e:
            print(f"Критическая ошибка в потоке сортировки: {e}")
        finally:
            self.window.write_event_value('-DONE-', '') # type: ignore

    def run(self):
        """Основной цикл событий GUI."""
        self.window['-MODEL-'].update(values=["Загрузка..."], value="Загрузка...", readonly=True) # type: ignore
        threading.Thread(target=self._load_models, daemon=True).start()

        while True:
            event, values = self.window.read(timeout=100) # type: ignore

            if event in (sg.WINDOW_CLOSED, 'Выход'):
                break
            
            if event == '-MODELS-LOADED-':
                models, selected = values['-MODELS-LOADED-']
                self.window['-MODEL-'].update(values=models, value=selected, readonly=False) # type: ignore

            if event == 'Обновить модели':
                self.window['-MODEL-'].update(values=["Загрузка..."], value="Загрузка...", readonly=True) # type: ignore
                threading.Thread(target=self._load_models, daemon=True).start()

            if event == 'Запуск':
                src, tgt, model = values['-SRC-'], values['-TGT-'], values['-MODEL-']
                if not all([src, tgt, model]):
                    sg.popup_error("Заполните все поля!")
                    continue
                
                self._save_last_model(model)

                if not self.ollama_manager.is_running():
                    print("Запуск сервера Ollama...")
                    if not self.ollama_manager.start():
                        continue
                    print("Сервер Ollama запущен.")

                self.window['-LOG-'].update("") # type: ignore
                self.window['-BAR-'].update(0, visible=True) # type: ignore
                threading.Thread(
                    target=self._run_sorting_thread,
                    args=(src, tgt, model),
                    daemon=True
                ).start()

            if event == '-PROGRESS-':
                v = values['-PROGRESS-']
                p = int(v['done'] / v['total'] * 100) if v['total'] else 0
                self.window['-BAR-'].update(p) # type: ignore
                print(v['msg'])

            if event == '-DONE-':
                sg.popup_ok("Сортировка завершена!")
                self.window['-BAR-'].update(0, visible=False) # type: ignore

        self.window.close() # type: ignore
        self.ollama_manager.stop()

if __name__ == '__main__':
    gui = GUI()
    gui.run() 