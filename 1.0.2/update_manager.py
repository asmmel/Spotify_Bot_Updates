import requests
import importlib
import os
import sys
import time

class UpdateManager:
    def __init__(self, config):
        self.config = config
        self.update_url = "https://asmmel.github.io/Spotify_Bot_Updates/"  # Замените на ваш URL
        self.version_file = "version.txt"
        self.last_check_file = "last_check.txt"

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
            response = requests.get(f"{self.update_url}{version}/{file}")
            if response.status_code == 200:
                with open(file, 'wb') as f:
                    f.write(response.content)

    def apply_update(self, version):
        with open(self.version_file, 'w') as f:
            f.write(version)
        
        # Перезагрузка обновленных модулей
        importlib.reload(sys.modules['spotify_bot_worker'])
        importlib.reload(sys.modules['config_manager'])
        
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
