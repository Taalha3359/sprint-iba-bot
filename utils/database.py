import json
import os

class UserDatabase:
    def __init__(self, file_path='data/users.json'):
        self.file_path = file_path
        self._ensure_data_file()
    
    def _ensure_data_file(self):
        # Create folder if it doesn't exist
        os.makedirs(os.path.dirname(self.file_path), exist_ok=True)
        if not os.path.exists(self.file_path):
            with open(self.file_path, 'w') as f:
                json.dump({}, f)
    
    def _read_data(self):
        with open(self.file_path, 'r') as f:
            return json.load(f)
    
    def _write_data(self, data):
        with open(self.file_path, 'w') as f:
            json.dump(data, f, indent=2)
    
    def get_user(self, user_id):
        data = self._read_data()
        return data.get(str(user_id))
    
    def create_user(self, user_id):
        data = self._read_data()
        user_data = {
            'total_score': 0,
            'math': {'correct': 0, 'total': 0, 'topics': {}},
            'english': {'correct': 0, 'total': 0, 'topics': {}},
            'analytical': {'correct': 0, 'total': 0, 'topics': {}}
        }
        data[str(user_id)] = user_data
        self._write_data(data)
        return user_data
    
    def update_user(self, user_id, user_data):
        data = self._read_data()
        data[str(user_id)] = user_data
        self._write_data(data)