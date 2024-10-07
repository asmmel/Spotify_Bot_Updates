import requests
import importlib
import os
import sys
import time
import configparser
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives import serialization
import zipfile
import io
import json
import base64

class EncryptedUpdateManager:
    def __init__(self, config):
        self.config = config
        self.update_url = "https://asmmel.github.io/Spotify_Bot_Updates/"
        self.version_file = "version.txt"
        self.last_check_file = "last_check.txt"
        self.config_file = "config.ini"
        self.update_dir = os.path.join(os.getenv('APPDATA'), 'SpotifyBot', 'Updates')
        os.makedirs(self.update_dir, exist_ok=True)
        self.key_file = os.path.join(self.update_dir, "encryption_key.bin")
        self.key = self.load_or_generate_key()
        self.cipher_suite = Fernet(self.key)
        self.public_key = self.load_public_key()

    def load_or_generate_key(self):
        if os.path.exists(self.key_file):
            with open(self.key_file, 'rb') as f:
                return f.read()
        else:
            key = Fernet.generate_key()
            with open(self.key_file, 'wb') as f:
                f.write(key)
            return key

    def load_public_key(self):
        public_key_path = os.path.join(self.update_dir, "public_key.pem")
        if not os.path.exists(public_key_path):
            response = requests.get(f"{self.update_url}public_key.pem")
            if response.status_code == 200:
                with open(public_key_path, 'wb') as f:
                    f.write(response.content)
            else:
                raise Exception("Failed to download public key")
        
        with open(public_key_path, 'rb') as key_file:
            return serialization.load_pem_public_key(key_file.read())

    def verify_signature(self, data, signature):
        try:
            self.public_key.verify(
                signature,
                data,
                padding.PSS(
                    mgf=padding.MGF1(hashes.SHA256()),
                    salt_length=padding.PSS.MAX_LENGTH
                ),
                hashes.SHA256()
            )
            return True
        except:
            return False

    def check_for_updates(self):
        try:
            with open(self.version_file, 'r') as f:
                current_version = f.read().strip()
        except FileNotFoundError:
            current_version = "0.0.0"

        response = requests.get(f"{self.update_url}latest_version.json")
        if response.status_code == 200:
            version_info = json.loads(response.text)
            latest_version = version_info['version']
            signature = base64.b64decode(version_info['signature'])
            if self.verify_signature(latest_version.encode(), signature):
                return latest_version != current_version, latest_version
            else:
                print("Invalid version signature")
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
        
        # Update modules
        sys.path.insert(0, self.update_dir)
        for module in ['spotify_bot_worker', 'config_manager']:
            if module in sys.modules:
                importlib.reload(sys.modules[module])
        sys.path.pop(0)

        # Update version
        with open(os.path.join(self.update_dir, self.version_file), 'r') as f:
            new_version = f.read().strip()

        # Update configuration
        self.update_config(os.path.join(self.update_dir, self.config_file))

        print(f"Update to version {new_version} completed.")
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
            print(f"Update to version {latest_version} is available")
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
        return (current_time - last_check) >= 24 * 60 * 60  # 24 hours in seconds

    def update_last_check_time(self):
        with open(self.last_check_file, 'w') as f:
            f.write(str(time.time()))