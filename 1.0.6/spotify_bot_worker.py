from PyQt5.QtCore import QThread, pyqtSignal
import time
import logging
from constants import *
import requests
import base64
import random
import uiautomator2 as u2
import telebot
import pyautogui as pg
import json
from datetime import datetime
import os
import socket
from typing import List, Dict, Optional, Union
import re
import asyncio
import concurrent.futures
from typing import List
import socket

# Константы
SPOTIFY_PACKAGE = "com.spotify.music"
SEARCH_TAB_RESOURCE_ID = f"{SPOTIFY_PACKAGE}:id/search_tab"
QUERY_RESOURCE_ID = f"{SPOTIFY_PACKAGE}:id/query"
CLEAR_QUERY_BUTTON_RESOURCE_ID = f"{SPOTIFY_PACKAGE}:id/clear_query_button"

class SpotifyBotWorker(QThread):
    update_signal = pyqtSignal(str)
    finished_signal = pyqtSignal()

    def __init__(self, config):
        super().__init__()
        self.config = config
        self.is_running = True
        self.devicelist: List[str] = []
        self.name_cache: Dict[str, Dict[str, Union[int, List[str]]]] = {}
        self.excluded_devices: List[str] = []  # Новый список для хранения исключенных устройств
        self.setup_logging()

    def setup_logging(self):
        logging.basicConfig(filename='spotify_bot.log', level=logging.INFO,
                            format='%(asctime)s - %(levelname)s - %(message)s')

    def run(self):
        self.update_signal.emit("Начало работы бота...")
        TOKEN = self.config['Telegram']['TOKEN']
        self.bot = telebot.TeleBot(TOKEN)

        token = self.config['Subscription']['TOKEN']
        if not self.check_token(token):
            self.update_signal.emit("Недействительный токен подписки.")
            self.finished_signal.emit()
            return

        self.devicelist = self.get_device_list(
            self.config['BlueStacks']['IP'],
            int(self.config['BlueStacks']['START_PORT']),
            int(self.config['BlueStacks']['END_PORT']),
            int(self.config['BlueStacks']['PORT_STEP'])
        )

        if not self.devicelist:
            self.update_signal.emit(f"Нет открытых портов на {self.config['BlueStacks']['IP']} в заданном диапазоне.")
            self.finished_signal.emit()
            return

        self.excluded_devices = []  # Сбрасываем список исключенных устройств при запуске

        with open(self.config['Database']['FILE_PATH'], 'r') as file:
            line_count = sum(1 for line in file)
        self.play_circles(line_count, token)
        self.finished_signal.emit()

    def stop(self):
        self.is_running = False

    def check_login_status(self, d: u2.Device, device: str) -> bool:
        try:
            if d(text="Sign up free").exists(timeout=5):
                self.update_signal.emit(f"Устройство {device} не залогинено")
                self.excluded_devices.append(device)
                self.send_telegram_notification(device)
                return False
            return True
        except Exception as e:
            self.update_signal.emit(f"Ошибка при проверке статуса логина: {str(e)}")
            return False

    def send_telegram_notification(self, device: str) -> None:
        try:
            screenshot_path = f'screenshot_{device.replace(":", "_")}.png'
            pg.screenshot(screenshot_path)
            with open(screenshot_path, 'rb') as img:
                chat_id = self.config['Telegram']['CHAT_ID']
                text = f'Устройство {device} не залогинено'
                self.bot.send_photo(chat_id, img, caption=text)
            os.remove(screenshot_path)  # Удаляем скриншот после отправки
        except Exception as e:
            self.update_signal.emit(f"Ошибка при отправке уведомления в Telegram: {str(e)}")

    def check_token(self, token: str) -> bool:
        try:
            response = requests.get(f"{SERVER_URL}{TOKENS_FILE_PATH}")
            if response.status_code == 200:
                valid_tokens = response.text.strip().split('\n')
                return token in valid_tokens
            else:
                self.update_signal.emit(f"Ошибка при получении файла токенов: {response.status_code}")
                return False
        except requests.RequestException as e:
            self.update_signal.emit(f"Ошибка при проверке токена: {e}")
            return False

    @staticmethod
    async def check_port_async(ip: str, port: int) -> bool:
        conn = asyncio.open_connection(ip, port)
        try:
            _, writer = await asyncio.wait_for(conn, timeout=0.5)
            writer.close()
            await writer.wait_closed()
            return True
        except (asyncio.TimeoutError, ConnectionRefusedError):
            return False

    async def check_ports_range_async(self, ip: str, start_port: int, end_port: int, step: int) -> List[int]:
        tasks = []
        for port in range(start_port, end_port, step):
            tasks.append(self.check_port_async(ip, port))
        results = await asyncio.gather(*tasks)
        return [start_port + i * step for i, is_open in enumerate(results) if is_open]

    def get_device_list_async(self, ip: str, start_port: int, end_port: int, step: int) -> List[str]:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        open_ports = loop.run_until_complete(self.check_ports_range_async(ip, start_port, end_port, step))
        loop.close()
        return [f'{ip}:{port}' for port in open_ports] if open_ports else []

    @staticmethod
    def check_port_thread(ip: str, port: int) -> bool:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(0.5)
            result = s.connect_ex((ip, port))
            return result == 0

    def get_device_list_thread(self, ip: str, start_port: int, end_port: int, step: int) -> List[str]:
        max_workers = int(self.config['BlueStacks'].get('MAX_WORKERS', 50))
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            ports = range(start_port, end_port, step)
            results = list(executor.map(lambda p: self.check_port_thread(ip, p), ports))
        open_ports = [start_port + i * step for i, is_open in enumerate(results) if is_open]
        return [f'{ip}:{port}' for port in open_ports] if open_ports else []

    # Оригинальный метод get_device_list (можно использовать любой из трех вариантов)
    def get_device_list(self, ip: str, start_port: int, end_port: int, step: int) -> List[str]:
        # Используем многопоточную версию по умолчанию
        return self.get_device_list_thread(ip, start_port, end_port, step)
        
        # Многопоточная версия
        # return self.get_device_list_thread(ip, start_port, end_port, step)
        
        # Оригинальная версия
        open_ports = []
        for port in range(start_port, end_port, step):
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(0.5)
                result = s.connect_ex((ip, port))
                if result == 0:
                    open_ports.append(port)
        return [f'{ip}:{port}' for port in open_ports] if open_ports else []

    def split_file(self, file_path: str, lines_per_file: int) -> None:
        small_file_number = 1
        with open(file_path, 'r') as big_file:
            for lineno, line in enumerate(big_file):
                if lineno % lines_per_file == 0:
                    if lineno != 0:
                        small_file.close()
                    small_file_name = f"database_part_{small_file_number}.txt"
                    small_file = open(small_file_name, 'w')
                    small_file_number += 1
                small_file.write(line)
            if 'small_file' in locals():
                small_file.close()

    def name(self, dev: str, file_number: int = 1) -> Optional[List[str]]:
        if dev not in self.name_cache:
            self.name_cache[dev] = {"count": 0, "lines": []}

        used_lines = self.name_cache[dev]["lines"]

        file_path = f"database_part_{file_number}.txt"
        if not os.path.exists(file_path):
            return None

        with open(file_path) as f:
            lines = [line.strip() for line in f if line.strip() not in used_lines]

        if not lines:
            return self.name(dev, file_number + 1)

        line = random.choice(lines)
        used_lines.append(line)
        self.name_cache[dev]["count"] += 1

        return [line]

    def is_app_running(self, d: u2.Device, package_name: str) -> bool:
        current_app = d.app_current()
        return current_app["package"] == package_name if current_app else False

    def restart_spotify(self, d: u2.Device) -> None:
        d.press('home') 
        d.app_stop(SPOTIFY_PACKAGE)
        time.sleep(5)
        d.app_start(SPOTIFY_PACKAGE, ".MainActivity")
        time.sleep(5)
        pid = d.app_wait(SPOTIFY_PACKAGE)
        if not pid:
            self.update_signal.emit(f"{SPOTIFY_PACKAGE} is not running")
        else:
            self.update_signal.emit(f"{SPOTIFY_PACKAGE} pid is {pid}")
        time.sleep(5)
        d(resourceId=f"{SPOTIFY_PACKAGE}:id/home_tab").click()
        time.sleep(2)
        search = d(resourceId=SEARCH_TAB_RESOURCE_ID)
        time.sleep(1)
        search.click()
        search.click()

    def handle_alert_or_perform_action(self, d: u2.Device) -> None:
        def check_and_close_alert():
            alert = d(text="BlueStacks Launcher isn't responding")
            if alert.exists():
                close_button = d(resourceId="android:id/aerr_close")
                if close_button.exists():
                    close_button.click(timeout=1)
                    return True
            return False

        if check_and_close_alert():
            self.update_signal.emit("Предупреждение 'BlueStacks Launcher isn't responding' закрыто")
            search = d(resourceId=SEARCH_TAB_RESOURCE_ID)
            time.sleep(1)
            search.click()
            search.click()
            
            # Дополнительная проверка после закрытия предупреждения
            time.sleep(2)  # Даем время на обновление UI
            if check_and_close_alert():
                self.update_signal.emit("Предупреждение появилось снова и было закрыто")
                d.click(d.window_size()[0] / 2, d.window_size()[1] / 2)
                self.update_signal.emit("Выполнен клик по центру экрана")
            else:
                self.update_signal.emit("Предупреждение успешно закрыто")
        else:
            self.update_signal.emit("Предупреждение 'BlueStacks Launcher isn't responding' не обнаружено")
            # Здесь нет сообщения о запуске альтернативной функции

    def process_exception(self, d: u2.Device, screenshot: bool = True) -> None:
        self.save_cache_to_file("cache_except.json")
        self.update_signal.emit('RESTART SPOTIFY')
        self.restart_spotify(d)
        if screenshot:
            pg.screenshot('screenshot.png')
            with open('screenshot.png', 'rb') as img:
                chat_id = self.config['Telegram']['CHAT_ID']
                text = 'Server Spotify Except'
                self.bot.send_photo(chat_id, img, caption=text)

    def search_and_play(self, d: u2.Device, name_artist: str) -> None:
        self.handle_alert_or_perform_action(d)
        if not name_artist.strip():
            self.update_signal.emit('Artist Name = NONE')
            return

        try:
            d.implicitly_wait(10.0)
            # Удалили проверку запуска приложения отсюда, так как она теперь выполняется в ensure_app_running
            
            d(resourceId=QUERY_RESOURCE_ID).click()
            time.sleep(1)
            d.send_keys(name_artist)
            time.sleep(2)
            artist_name = name_artist.split()[-1]
            search_text = f"Song • {artist_name}"
            
            self.update_signal.emit(f"Ищем: {search_text}")

            song_element = d(textMatches=f"(?i)Song • .*{re.escape(artist_name)}.*")
            
            if song_element.exists():
                self.update_signal.emit(f"Найдена песня: {song_element.get_text()}")
                song_element.click()
            else:
                d.xpath('//*[@resource-id="com.spotify.music:id/search_content_recyclerview"]/android.view.ViewGroup[1]').click()
                time.sleep(1)
                self.update_signal.emit(f"Песня с '{artist_name}' не найдена. Выбираем первый результат.")
                d.xpath('//*[@resource-id="com.spotify.music:id/search_content_recyclerview"]/android.view.ViewGroup[1]').click()

            time.sleep(1.5)
            d(resourceId=CLEAR_QUERY_BUTTON_RESOURCE_ID).click()
            time.sleep(1)

        except u2.exceptions.UiObjectNotFoundError:
            self.update_signal.emit("Элемент не найден")
            self.process_exception(d)
        except u2.exceptions.XPathElementNotFoundError:
            self.update_signal.emit("XPath элемент не найден")
            self.process_exception(d)
        except u2.exceptions.UiAutomationNotConnectedError:
            self.update_signal.emit("UI Automation не подключен")
            self.process_exception(d)
        except RuntimeError as e:
            if "USB device" in str(e) and "is offline" in str(e):
                logging.error(f"RuntimeError: {e}")
        except Exception as ex:
            self.update_signal.emit(str(ex))
            logging.exception("Произошло исключение:")
            self.process_exception(d, screenshot=True)

    def ensure_app_running(self, d: u2.Device) -> bool:
        max_attempts = 3
        for attempt in range(max_attempts):
            if self.is_app_running(d, SPOTIFY_PACKAGE):
                return True
            
            self.update_signal.emit(f"Попытка {attempt + 1}/{max_attempts}: Приложение {SPOTIFY_PACKAGE} не запущено. Запускаем...")
            self.restart_spotify(d)
            time.sleep(10)
        
        self.update_signal.emit(f"Не удалось запустить приложение {SPOTIFY_PACKAGE} после {max_attempts} попыток.")
        return False

    def play_circles(self, circles: int, token: str) -> None:
        self.update_signal.emit(f'Начало воспроизведения {circles} кругов')
        self.split_file(self.config['Database']['FILE_PATH'], int(self.config['Database']['SPLIT_LINES']))
        for qwe in range(circles):
            if not self.is_running:
                self.update_signal.emit("Работа бота остановлена")
                return
            if not self.check_token(token):
                self.update_signal.emit("Токен недействителен или срок его действия истек.")
                return
            timestamp_start = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self.update_signal.emit(f"Начало Spotify: [{timestamp_start}]")
            for device in self.devicelist:
                if device not in self.excluded_devices:
                    d = u2.connect(device)
                    if self.check_login_status(d, device):
                        if self.ensure_app_running(d):  # Проверяем и запускаем приложение
                            result = self.name(device)
                            name_artist = result[0] if result else None
                            if name_artist is not None:
                                self.search_and_play(d, name_artist)
                        else:
                            self.update_signal.emit(f"Пропуск устройства {device} из-за проблем с запуском приложения")
                else:
                    self.update_signal.emit(f"Устройство {device} пропущено (исключено)")
            timestamp_finish = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self.update_signal.emit(f"Завершение Spotify: [{timestamp_finish}]")
        self.update_signal.emit("Все круги завершены")

    def save_cache_to_file(self, filename: str) -> None:
        with open(filename, "w") as f:
            json.dump(self.name_cache, f, indent=4)