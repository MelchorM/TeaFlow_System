from models import AuthModel


class AuthController:
    def __init__(self, auth_model=None):
        self.auth_model = auth_model or AuthModel()

    def authenticate(self, username, password):
        return self.auth_model.authenticate(username, password)

    def reset_password(self, username, new_password):
        return self.auth_model.reset_password(username, new_password)
