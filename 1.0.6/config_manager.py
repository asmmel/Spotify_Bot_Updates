import configparser

class ConfigManager:
    def __init__(self):
        self.config = configparser.ConfigParser()
        self.load_config()

    def load_config(self):
        try:
            self.config.read('config.ini')
            # Добавляем значение по умолчанию, если оно отсутствует
            if 'BlueStacks' not in self.config:
                self.config['BlueStacks'] = {}
            if 'MAX_WORKERS' not in self.config['BlueStacks']:
                self.config['BlueStacks']['MAX_WORKERS'] = '50'
                self.save_config()
        except configparser.Error as e:
            print(f"Не удалось загрузить конфигурацию: {e}")

    def save_config(self):
        with open('config.ini', 'w') as configfile:
            self.config.write(configfile)

    def get_settings(self):
        return {section: dict(self.config[section]) for section in self.config.sections()}

    def update_setting(self, section, key, value):
        if section not in self.config:
            self.config[section] = {}
        self.config[section][key] = value

    def get_setting(self, section, key):
        return self.config[section][key]