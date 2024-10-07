import requests
import importlib
import os
import sys
import time
import configparser

class UpdateManager:
    def __init__(self, config):
        self.config = config
        self.update_url = "https://asmmel.github.io/Spotify_Bot_Updates/"  # Замените на ваш URL
        self.version_file = "version.txt"
        self.last_check_file = "last_check.txt"
        self.config_file = "config.ini"  # Имя файла конфигурации


    def check_for_updates(self):
        try:
            with open(self.version_file, 'r') as f:
                current_version = f.read().strip()
        except FileNotFoundError:
            current_version = "0.0.0"

        response = requests.get(f"{self.update_url}latest_version.txt")
        if response.status_code == 200:
            latest_version = response.text.strip()
            return latest_version != current_version, latest_version
        return False, current_version

    def download_update(self, version):
        files_to_update = requests.get(f"{self.update_url}{version}/files.txt").text.split('\n')
        for file in files_to_update:
            if file.strip():  # Пропускаем пустые строки
                response = requests.get(f"{self.update_url}{version}/{file}")
                if response.status_code == 200:
                    if file == self.config_file:
                        self.update_config(response.text)
                    else:
                        with open(file, 'wb') as f:
                            f.write(response.content)

    def update_config(self, new_config_content):
        new_config = configparser.ConfigParser()
        new_config.read_string(new_config_content)

        current_config = configparser.ConfigParser()
        current_config.read(self.config_file)

        for section in new_config.sections():
            if not current_config.has_section(section):
                current_config.add_section(section)
            for key, value in new_config.items(section):
                if not current_config.has_option(section, key) or \
                   current_config.get(section, key).startswith('YOUR_'):
                    current_config.set(section, key, value)

        with open(self.config_file, 'w') as configfile:
            current_config.write(configfile)

        # Обновляем конфиг, сохраняя пользовательские настройки
        for section in new_config.sections():
            if not current_config.has_section(section):
                current_config.add_section(section)
            for key, value in new_config.items(section):
                if not current_config.has_option(section, key):
                    current_config.set(section, key, value)

        # Сохраняем обновленный конфиг
        with open(self.config_file, 'w') as configfile:
            current_config.write(configfile)

    def apply_update(self, version):
        with open(self.version_file, 'w') as f:
            f.write(version)
        
        # Перезагрузка обновленных модулей
        modules_to_reload = ['spotify_bot_worker', 'config_manager']
        for module in modules_to_reload:
            if module in sys.modules:
                importlib.reload(sys.modules[module])
        
        print(f"Обновление до версии {version} завершено.")

    def update_if_available(self):
        if self.should_check_update():
            update_available, latest_version = self.check_for_updates()
            if update_available:
                print(f"Доступно обновление до версии {latest_version}")
                self.download_update(latest_version)
                self.apply_update(latest_version)
                return True
            self.update_last_check_time()
        return False

    def should_check_update(self):
        try:
            with open(self.last_check_file, 'r') as f:
                last_check = float(f.read().strip())
        except FileNotFoundError:
            return True

        current_time = time.time()
        return (current_time - last_check) >= 24 * 60 * 60  # 24 часа в секундах

    def update_last_check_time(self):
        with open(self.last_check_file, 'w') as f:
            f.write(str(time.time()))
