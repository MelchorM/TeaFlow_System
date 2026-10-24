import sys
import os
from PyQt5.QtWidgets import QApplication
from controllers.app_controller import AppController


def main():
    app = QApplication(sys.argv)
    window = AppController().build_main_window()
    if str(os.getenv("BESTBREW_FIXED_WINDOW", "")).strip().lower() in {"1", "true", "yes", "on"}:
        window.show()
    else:
        window.showMaximized()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
    
