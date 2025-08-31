import json
import os
from datetime import datetime, timedelta

class UserDatabase:
    def __init__(self, file_path='data/users.json'):
        self.file_path = file_path
        self._ensure_data_file()
    
    def _ensure_data_file(self):
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
        user_data = data.get(str(user_id), {})
        
        # Set default values if not present
        defaults = {
            'total_score': 0,
            'questions_answered': 0,
            'premium_access': False,
            'premium_until': None,
            'is_admin': False,
            'math': {'correct': 0, 'total': 0, 'topics': {}},
            'english': {'correct': 0, 'total': 0, 'topics': {}},
            'analytical': {'correct': 0, 'total': 0, 'topics': {}}
        }
        
        for key, value in defaults.items():
            if key not in user_data:
                user_data[key] = value
        
        return user_data
    
    def create_user(self, user_id):
        data = self._read_data()
        user_data = {
            'total_score': 0,
            'questions_answered': 0,
            'premium_access': False,
            'premium_until': None,
            'is_admin': False,
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
        print(f"📝 Updating user {user_id}: questions_answered = {user_data.get('questions_answered', 0)}")
        self._write_data(data)
    
    def increment_questions_answered(self, user_id):
    data = self._read_data()
    user_id_str = str(user_id)
    
    if user_id_str not in data:
        data[user_id_str] = {}
    
    user_data = data[user_id_str]
    current_count = user_data.get('questions_answered', 0)
    user_data['questions_answered'] = current_count + 1
    
    print(f"📊 DEBUG: User {user_id} questions answered: {current_count} -> {user_data['questions_answered']}")
    
    self._write_data(data)
    return user_data['questions_answered']
    
    def add_premium_access(self, user_id, days):
        user_data = self.get_user(user_id)
        if user_data['premium_until']:
            current_end = datetime.fromisoformat(user_data['premium_until'])
            new_end = current_end + timedelta(days=days)
        else:
            new_end = datetime.now() + timedelta(days=days)
        
        user_data['premium_until'] = new_end.isoformat()
        user_data['premium_access'] = True
        self.update_user(user_id, user_data)
        return new_end
    
    def check_premium_status(self, user_id):
        user_data = self.get_user(user_id)
        if user_data['premium_until']:
            premium_until = datetime.fromisoformat(user_data['premium_until'])
            if datetime.now() > premium_until:
                user_data['premium_access'] = False
                user_data['premium_until'] = None
                self.update_user(user_id, user_data)
        return user_data['premium_access']
    
    def set_admin(self, user_id, is_admin):
        user_data = self.get_user(user_id)
        user_data['is_admin'] = is_admin
        self.update_user(user_id, user_data)


