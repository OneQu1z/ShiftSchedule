import json
import os

USERS_FILE = "data/users.json"


class UserManager:
    def __init__(self):
        self.users_file = USERS_FILE
        self._ensure_file(self.users_file)

    def _ensure_file(self, filename):
        if not os.path.exists(filename):
            with open(filename, "w") as f:
                json.dump([], f)

    def load_users(self):
        try:
            with open(self.users_file, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            return []

    def save_user(self, chat_id):
        users = self.load_users()
        if chat_id not in users:
            users.append(chat_id)
            with open(self.users_file, "w") as f:
                json.dump(users, f)
            return True
        return False

