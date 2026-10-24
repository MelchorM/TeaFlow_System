from views.login_view import LoginView


class AppController:
    def __init__(self):
        self.login_window = None

    def build_main_window(self):
        self.login_window = LoginView()
        return self.login_window
