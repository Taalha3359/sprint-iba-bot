import os
from pymongo import MongoClient
from datetime import datetime, timedelta
import json

class UserDatabase:
    def __init__(self):
        # Get connection string from environment variable
        self.connection_string = os.getenv('MONGODB_URI')
        if not self.connection_string:
            raise ValueError("MONGODB_URI environment variable is not set")
        
        # ADD PROPER TIMEOUT PARAMETERS - THIS IS CRITICAL
        if "?" in self.connection_string:
            self.connection_string += "&connectTimeoutMS=10000&socketTimeoutMS=10000&serverSelectionTimeoutMS=10000"
        else:
            self.connection_string += "?connectTimeoutMS=10000&socketTimeoutMS=10000&serverSelectionTimeoutMS=10000"
        
        print(f"Connecting with: {self.connection_string.split('@')[1] if '@' in self.connection_string else self.connection_string}")
        
        try:
            self.client = MongoClient(self.connection_string, serverSelectionTimeoutMS=10000)
            # Test connection immediately
            self.client.admin.command('ping')
            self.db = self.client.sprint_bot
            self.users = self.db.users
            print("✅ Successfully connected to MongoDB Atlas")
        except Exception as e:
            print(f"❌ MongoDB connection failed: {e}")
            # Fallback to in-memory storage if MongoDB fails
            self.fallback_mode = True
            self.fallback_data = {}
            print("🔄 Using fallback in-memory storage")
    
    def get_user(self, user_id):
        if hasattr(self, 'fallback_mode') and self.fallback_mode:
            # Use fallback in-memory storage
            return self.fallback_data.get(str(user_id), self.create_user(user_id))
        
        try:
            user_data = self.users.find_one({'_id': str(user_id)})  # Use _id for MongoDB
            if not user_data:
                return self.create_user(user_id)
            
            # Remove MongoDB's _id field to avoid serialization issues
            user_data.pop('_id', None)
            return user_data
            
        except Exception as e:
            print(f"❌ MongoDB error in get_user: {e}")
            # Fallback to in-memory storage
            if not hasattr(self, 'fallback_mode'):
                self.fallback_mode = True
                self.fallback_data = {}
            return self.fallback_data.get(str(user_id), self.create_user(user_id))
    
    def create_user(self, user_id):
        """YOUR EXISTING create_user METHOD - KEEP THIS AS IS"""
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
        
        if hasattr(self, 'fallback_mode') and self.fallback_mode:
            # Store in fallback memory
            self.fallback_data[str(user_id)] = user_data
            return user_data
        
        try:
            # Store in MongoDB with _id field
            mongo_data = user_data.copy()
            mongo_data['_id'] = str(user_id)
            self.users.insert_one(mongo_data)
            return user_data
        except Exception as e:
            print(f"❌ MongoDB create_user failed: {e}")
            # Fallback to in-memory storage
            if not hasattr(self, 'fallback_mode'):
                self.fallback_mode = True
                self.fallback_data = {}
            self.fallback_data[str(user_id)] = user_data
            return user_data
    
    def update_user(self, user_id, user_data):
        if hasattr(self, 'fallback_mode') and self.fallback_mode:
            # Use fallback in-memory storage
            self.fallback_data[str(user_id)] = user_data
            print(f"📝 Updated user {user_id} in fallback storage")
            return
        
        try:
            update_data = user_data.copy()
            self.users.update_one(
                {'_id': str(user_id)},
                {'$set': update_data},
                upsert=True
            )
            print(f"📝 Updated user {user_id} in MongoDB")
        except Exception as e:
            print(f"❌ MongoDB update failed: {e}")
            # Fallback to in-memory storage
            if not hasattr(self, 'fallback_mode'):
                self.fallback_mode = True
                self.fallback_data = {}
            self.fallback_data[str(user_id)] = user_data
    
    def increment_questions_answered(self, user_id):
        if hasattr(self, 'fallback_mode') and self.fallback_mode:
            user_data = self.fallback_data.get(str(user_id), self.create_user(user_id))
            user_data['questions_answered'] = user_data.get('questions_answered', 0) + 1
            self.fallback_data[str(user_id)] = user_data
            return user_data['questions_answered']
        
        try:
            result = self.users.update_one(
                {'_id': str(user_id)},
                {'$inc': {'questions_answered': 1}},
                upsert=True
            )
            user_data = self.get_user(user_id)
            print(f"📊 User {user_id} questions answered: {user_data['questions_answered']}")
            return user_data['questions_answered']
        except Exception as e:
            print(f"❌ MongoDB increment failed: {e}")
            # Fallback to in-memory storage
            if not hasattr(self, 'fallback_mode'):
                self.fallback_mode = True
                self.fallback_data = {}
            user_data = self.fallback_data.get(str(user_id), self.create_user(user_id))
            user_data['questions_answered'] = user_data.get('questions_answered', 0) + 1
            self.fallback_data[str(user_id)] = user_data
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



