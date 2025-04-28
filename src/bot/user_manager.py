import json
from pathlib import Path

class UserManager:
    def __init__(self):
        # Используем абсолютные пути
        base_dir = Path(__file__).parent.parent.parent
        self.users_file = base_dir / "data" / "users.json"
        self.pending_users_file = base_dir / "data" / "pending_users.json"

        self._ensure_file(self.users_file)
        self._ensure_file(self.pending_users_file)

    def _ensure_file(self, filename):
        filename.parent.mkdir(parents=True, exist_ok=True)
        if not filename.exists():
            with open(filename, "w", encoding="utf-8") as f:  # FIXED: Добавлена кодировка
                json.dump([], f, ensure_ascii=False)  # FIXED: Отключен Unicode-escape

    def load_users(self):
        try:
            with open(self.users_file, "r", encoding="utf-8") as f:  # FIXED: Указана кодировка
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            return []

    def load_pen_users(self):
        try:
            with open(self.pending_users_file, "r", encoding="utf-8") as f:  # FIXED: Указана кодировка
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            return []

    def save_user(self, chat_id, username=None, name=None, fio=None):
        users = self.load_users()

        user_exists = any(user.get('chat_id') == chat_id for user in users)

        if not user_exists:
            new_user = {
                'chat_id': chat_id,
                'username': username,
                'name': name,
                'fio': fio,
                'approved': False
            }
            users.append(new_user)
            self._save_users(users)
            return True
        return False

    def update_user_fio(self, chat_id, fio):
        users = self.load_users()
        for user in users:
            if user.get('chat_id') == chat_id:
                user['fio'] = fio
                self._save_users(users)
                return True
        return False

    def get_user_by_fio(self, fio):
        users = self.load_users()
        for user in users:
            if user.get('fio') == fio:
                return user
        return None

    def load_pending_users(self):
        try:
            with open(self.pending_users_file, "r", encoding="utf-8") as f:  # FIXED: Указана кодировка
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            return []

    def save_pending_user(self, chat_id):
        pending_users = self.load_pending_users()
        if chat_id not in pending_users:
            pending_users.append(chat_id)
            with open(self.pending_users_file, "w", encoding="utf-8") as f:  # FIXED
                json.dump(pending_users, f, ensure_ascii=False)  # FIXED: Отключен Unicode-escape
            return True
        return False

    def accept_user(self, chat_id):
        pending_users = self.load_pending_users()
        if chat_id in pending_users:
            pending_users.remove(chat_id)
            with open(self.pending_users_file, "w", encoding="utf-8") as f:  # FIXED
                json.dump(pending_users, f, ensure_ascii=False)  # FIXED

        users = self.load_users()
        for user in users:
            if user.get('chat_id') == chat_id:
                user['approved'] = True
                self._save_users(users)
                return True

        new_user = {
            'chat_id': chat_id,
            'approved': True
        }
        users.append(new_user)
        self._save_users(users)
        return True

    def deny_user(self, chat_id):
        removed = False

        pending_users = self.load_pending_users()
        if chat_id in pending_users:
            pending_users.remove(chat_id)
            with open(self.pending_users_file, "w", encoding="utf-8") as f:  # FIXED
                json.dump(pending_users, f, ensure_ascii=False)  # FIXED
            removed = True

        users = self.load_users()
        new_users = [user for user in users if user.get('chat_id') != chat_id]

        if len(new_users) < len(users):
            self._save_users(new_users)
            removed = True

        return removed

    def is_approved(self, chat_id):
        users = self.load_users()
        return any(user.get('chat_id') == chat_id and user.get('approved') for user in users)

    def add_user_info(self, chat_id, username, name):
        users = self.load_users()
        for user in users:
            if user.get('chat_id') == chat_id:
                user['username'] = username
                user['name'] = name
                self._save_users(users)
                return True
        return False

    def get_user_info(self, chat_id):
        users = self.load_users()
        for user in users:
            if user.get('chat_id') == chat_id:
                return user
        return None

    def _save_users(self, users):
        with open(self.users_file, "w", encoding="utf-8") as f:  # FIXED: Указана кодировка
            json.dump(users, f, indent=2, ensure_ascii=False)  # FIXED: Отключен Unicode-escape