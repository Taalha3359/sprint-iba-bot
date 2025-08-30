import json
import os

class Leaderboard:
    def __init__(self, file_path='data/leaderboard.json'):
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
    
    def update_score(self, user_id, score):
        data = self._read_data()
        data[str(user_id)] = score
        self._write_data(data)
    
    def get_leaderboard(self):
        data = self._read_data()
        # Sort by score (highest first)
        sorted_data = sorted(data.items(), key=lambda x: x[1], reverse=True)
        return sorted_data