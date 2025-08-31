import os
from pymongo import MongoClient
from datetime import datetime, timedelta
import json

class UserDatabase:
    def __init__(self):
        # Get connection string from environment variable
        self.connection_string = os.getenv('MONGODB_URI', 'your_connection_string_here')
        self.client = MongoClient(self.connection_string)
        self.db = self.client.sprint_bot
        self.users = self.db.users
    
    def get_user(self, user_id):
        user_data = self.users.find_one({'_id': str(user_id)})
        if not user_data:
            return self.create_user(user_id)
        
        # Remove MongoDB's _id field to avoid serialization issues
        user_data.pop('_id', None)
        return user_data
    
    def create_user(self, user_id):
        user_data = {
            '_id': str(user_id),
            'total_score': 0,
            'questions_answered': 0,
            'premium_access': False,
            'premium_until': None,
            'is_admin': False,
            'math': {'correct': 0, 'total': 0, 'topics': {}},
            'english': {'correct': 0, 'total': 0, 'topics': {}},
            'analytical': {'correct': 0, 'total': 0, 'topics': {}}
        }
        self.users.insert_one(user_data.copy())  # Insert copy to avoid modifying
        user_data.pop('_id', None)  # Remove _id for return
        return user_data
    
    def update_user(self, user_id, user_data):
        # Create copy without _id for update
        update_data = user_data.copy()
        self.users.update_one(
            {'_id': str(user_id)},
            {'$set': update_data},
            upsert=True
        )
        print(f"📝 Updating user {user_id} in MongoDB")
    
    def increment_questions_answered(self, user_id):
        result = self.users.update_one(
            {'_id': str(user_id)},
            {'$inc': {'questions_answered': 1}},
            upsert=True
        )
        user_data = self.get_user(user_id)
        print(f"📊 DEBUG: User {user_id} questions answered: {user_data['questions_answered']}")
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
                return False
            return True
        return False
    
    def set_admin(self, user_id, is_admin):
        user_data = self.get_user(user_id)
        user_data['is_admin'] = is_admin
        self.update_user(user_id, user_data)

    def get_user(self, user_id):
        try:
            user_data = self.users.find_one({'_id': str(user_id)})
            if not user_data:
                return self.create_user(user_id)
            
            # Remove MongoDB's _id field to avoid serialization issues
            user_data.pop('_id', None)
            return user_data
            
        except Exception as e:
            print(f"❌ MongoDB error in get_user: {e}")
            # Return default user data if MongoDB fails
            return {
                'total_score': 0,
                'questions_answered': 0,
                'premium_access': False,
                'premium_until': None,
                'is_admin': False,
                'math': {'correct': 0, 'total': 0, 'topics': {}},
                'english': {'correct': 0, 'total': 0, 'topics': {}},
                'analytical': {'correct': 0, 'total': 0, 'topics': {}}
            }


