import sys
from PyQt5.QtWidgets import QApplication
from spotify_bot_gui import SpotifyBotGUI

if __name__ == '__main__':
    app = QApplication(sys.argv)
    ex = SpotifyBotGUI()
    ex.show()
    sys.exit(app.exec_())
