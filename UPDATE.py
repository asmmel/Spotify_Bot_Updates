import os
import json
import zipfile
import base64
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives import serialization

# Конфигурация
UPDATE_VERSION = "1.0.6"
BASE_DIR = r"Spotify_Bot_Updates"
UPDATE_DIR = os.path.join(BASE_DIR, UPDATE_VERSION)
PRIVATE_KEY_PATH = os.path.join(BASE_DIR, "private_key.pem")
ENCRYPTION_KEY_PATH = os.path.join(BASE_DIR, "encryption_key.bin")

# 1. Создание списка файлов для обновления
def create_files_list():
    files = os.listdir(UPDATE_DIR)
    with open(os.path.join(UPDATE_DIR, "files.txt"), "w") as f:
        for file in files:
            if file != "files.txt":
                f.write(f"{file}\n")
    return files

# 2. Создание и шифрование ZIP-архива
def create_encrypted_zip(files):
    zip_path = os.path.join(BASE_DIR, f"update_{UPDATE_VERSION}.zip")
    with zipfile.ZipFile(zip_path, 'w') as zipf:
        for file in files:
            zipf.write(os.path.join(UPDATE_DIR, file), file)
    
    with open(ENCRYPTION_KEY_PATH, "rb") as key_file:
        key = key_file.read()
    fernet = Fernet(key)
    
    with open(zip_path, "rb") as file:
        encrypted_data = fernet.encrypt(file.read())
    
    encrypted_zip_path = f"{zip_path}.enc"
    with open(encrypted_zip_path, "wb") as file:
        file.write(encrypted_data)
    
    os.remove(zip_path)  # Удаляем незашифрованный архив
    return encrypted_zip_path

# 3. Обновление latest_version.json
def update_version_json():
    with open(PRIVATE_KEY_PATH, "rb") as key_file:
        private_key = serialization.load_pem_private_key(
            key_file.read(),
            password=None
        )
    
    signature = private_key.sign(
        UPDATE_VERSION.encode(),
        padding.PSS(
            mgf=padding.MGF1(hashes.SHA256()),
            salt_length=padding.PSS.MAX_LENGTH
        ),
        hashes.SHA256()
    )
    
    version_info = {
        "version": UPDATE_VERSION,
        "signature": base64.b64encode(signature).decode()
    }
    
    with open(os.path.join(BASE_DIR, "latest_version.json"), "w") as f:
        json.dump(version_info, f)

# Выполнение процесса
if __name__ == "__main__":
    files = create_files_list()
    encrypted_zip_path = create_encrypted_zip(files)
    update_version_json()
    print(f"Обновление {UPDATE_VERSION} подготовлено успешно.")
    print(f"Зашифрованный архив: {encrypted_zip_path}")
    print("latest_version.json обновлен.")