import requests
import importlib
import os
import sys
import time
import configparser
from cryptography.fernet import Fernet
import zipfile
import io

class EncryptedUpdateManager:
    def __init__(self, config):
        self.config = config
        self.update_url = "https://asmmel.github.io/Spotify_Bot_Updates/"
        self.version_file = "version.txt"
        self.last_check_file = "last_check.txt"
        self.config_file = "config.ini"
        self.update_dir = os.path.join(os.getenv('APPDATA'), 'SpotifyBot', 'Updates')
        os.makedirs(self.update_dir, exist_ok=True)
        self.key = b'YOUR_SECRET_KEY_HERE'  # Замените на ваш секретный ключ
        self.cipher_suite = Fernet(self.key)

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
        encrypted_update_path = os.path.join(self.update_dir, f"update_{version}.zip.enc")
        response = requests.get(f"{self.update_url}{version}/update.zip.enc")
        if response.status_code == 200:
            with open(encrypted_update_path, 'wb') as f:
                f.write(response.content)
        return encrypted_update_path

    def apply_update(self, version, encrypted_update_path):
        with open(encrypted_update_path, 'rb') as f:
            encrypted_data = f.read()
        
        decrypted_data = self.cipher_suite.decrypt(encrypted_data)
        
        with io.BytesIO(decrypted_data) as virtual_file:
            with zipfile.ZipFile(virtual_file) as zf:
                zf.extractall(self.update_dir)
        
        # Обновляем модули
        sys.path.insert(0, self.update_dir)
        for module in ['spotify_bot_worker', 'config_manager']:
            if module in sys.modules:
                importlib.reload(sys.modules[module])
        sys.path.pop(0)

        # Обновляем версию
        with open(os.path.join(self.update_dir, self.version_file), 'r') as f:
            new_version = f.read().strip()

        # Обновляем конфигурацию
        self.update_config(os.path.join(self.update_dir, self.config_file))

        print(f"Обновление до версии {new_version} завершено.")
        return new_version

    def update_config(self, new_config_path):
        new_config = configparser.ConfigParser()
        new_config.read(new_config_path)

        current_config = configparser.ConfigParser()
        current_config.read(self.config_file)

        for section in new_config.sections():
            if not current_config.has_section(section):
                current_config.add_section(section)
            for key, value in new_config.items(section):
                if not current_config.has_option(section, key):
                    current_config.set(section, key, value)

        with open(self.config_file, 'w') as configfile:
            current_config.write(configfile)

    def update_if_available(self):
        update_available, latest_version = self.check_for_updates()
        if update_available:
            print(f"Доступно обновление до версии {latest_version}")
            encrypted_update_path = self.download_update(latest_version)
            new_version = self.apply_update(latest_version, encrypted_update_path)
            return True, new_version
        return False, None

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