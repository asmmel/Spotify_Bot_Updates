from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QPushButton, QLabel, QTextEdit, 
                             QHBoxLayout, QStatusBar, QMessageBox, QLineEdit, QFormLayout)
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QIcon
from spotify_bot_worker import SpotifyBotWorker
from config_manager import ConfigManager
from update_manager import EncryptedUpdateManager  # Обновленный импорт
import os
import sys

def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")

    return os.path.join(base_path, relative_path)

class SpotifyBotGUI(QWidget):
    def __init__(self):
        super().__init__()
        self.config_manager = ConfigManager()
        self.update_manager = EncryptedUpdateManager(self.config_manager.config)
        self.init_ui()
        self.worker = None
        self.setup_update_timer()

    def init_ui(self):
        layout = QVBoxLayout()

        # Заголовок
        title_label = QLabel("SPOTIFY BOT")
        title_label.setObjectName("title")
        title_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(title_label)

        # Кнопки
        button_layout = QHBoxLayout()
        
        self.start_button = QPushButton('Запустить')
        self.start_button.setIcon(QIcon(resource_path('play_icon.png')))
        self.start_button.clicked.connect(self.start_bot)
        button_layout.addWidget(self.start_button)

        self.stop_button = QPushButton('Остановить')
        self.stop_button.setIcon(QIcon(resource_path('stop_icon.png')))
        self.stop_button.clicked.connect(self.stop_bot)
        self.stop_button.setEnabled(False)
        button_layout.addWidget(self.stop_button)

        self.settings_button = QPushButton('Настройки')
        self.settings_button.setIcon(QIcon(resource_path('settings_icon.png')))
        self.settings_button.clicked.connect(self.toggle_settings)
        button_layout.addWidget(self.settings_button)

        layout.addLayout(button_layout)

        # Область для логов/настроек
        self.content_area = QTextEdit()
        self.content_area.setReadOnly(True)
        layout.addWidget(self.content_area)

        # Область настроек (изначально скрыта)
        self.settings_area = QWidget()
        self.settings_layout = QFormLayout()
        self.settings_area.setLayout(self.settings_layout)
        self.settings_area.hide()
        layout.addWidget(self.settings_area)

        # Кнопка сохранения настроек (изначально скрыта)
        self.save_settings_button = QPushButton('Сохранить настройки')
        self.save_settings_button.clicked.connect(self.save_settings)
        self.save_settings_button.hide()
        layout.addWidget(self.save_settings_button)

        # Статус-бар
        self.status_bar = QStatusBar()
        self.status_bar.showMessage("Готов к запуску")
        layout.addWidget(self.status_bar)

        self.setLayout(layout)
        self.setWindowTitle('Spotify Bot')
        self.setGeometry(300, 300, 500, 400)

        # Загрузка стилей из файла
        style_path = resource_path('styles.qss')
        if os.path.exists(style_path):
            with open(style_path, 'r') as f:
                self.setStyleSheet(f.read())
        else:
            print(f"Файл стилей не найден: {style_path}")

    def start_bot(self):
        self.start_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        self.settings_button.setEnabled(False)
        self.content_area.clear()
        self.content_area.append("Бот запущен")
        self.status_bar.showMessage("Бот работает")
        self.settings_area.hide()
        self.save_settings_button.hide()
        
        self.worker = SpotifyBotWorker(self.config_manager.config)
        self.worker.update_signal.connect(self.update_log)
        self.worker.finished_signal.connect(self.on_bot_finished)
        self.worker.start()

    def stop_bot(self):
        if self.worker:
            self.worker.stop()
        self.on_bot_finished()

    def on_bot_finished(self):
        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self.settings_button.setEnabled(True)
        self.content_area.append("Бот остановлен")
        self.status_bar.showMessage("Готов к запуску")

    def update_log(self, message):
        self.content_area.append(message)

    def toggle_settings(self):
        if self.settings_area.isVisible():
            self.settings_area.hide()
            self.save_settings_button.hide()
            self.content_area.show()
        else:
            self.show_settings()

    def show_settings(self):
        self.content_area.hide()
        self.settings_layout.removeWidget(self.settings_area)
        for i in reversed(range(self.settings_layout.count())): 
            self.settings_layout.itemAt(i).widget().setParent(None)

        settings = self.config_manager.get_settings()
        self.setting_inputs = {}
        for section, options in settings.items():
            for key, value in options.items():
                label = QLabel(f"{section} - {key}:")
                input_field = QLineEdit(str(value))
                self.setting_inputs[(section, key)] = input_field
                self.settings_layout.addRow(label, input_field)

        self.settings_area.show()
        self.save_settings_button.show()
    
    def setup_update_timer(self):
        self.update_timer = QTimer(self)
        self.update_timer.timeout.connect(self.check_for_updates)
        self.update_timer.start(24 * 60 * 60 * 1000)  # Проверка каждые 24 часа
        self.check_for_updates()  # Проверяем обновления при запуске

    def check_for_updates(self):
        if self.update_manager.should_check_update():
            update_available, new_version = self.update_manager.update_if_available()
            if update_available:
                QMessageBox.information(self, "Обновление", f"Бот был успешно обновлен до версии {new_version}. Перезапустите приложение для применения обновлений.")
                self.close()
            else:
                self.status_bar.showMessage("Обновлений не найдено")
            self.update_manager.update_last_check_time()

    def save_settings(self):
        for (section, key), input_field in self.setting_inputs.items():
            self.config_manager.update_setting(section, key, input_field.text())
        self.config_manager.save_config()
        QMessageBox.information(self, "Успех", "Настройки сохранены")

    def update_log(self, message):
        self.content_area.append(message)