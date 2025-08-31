# database_mongo.py
import motor.motor_asyncio
from datetime import datetime, timedelta
import os

class MongoDB:
    def __init__(self):
        self.mongo_uri = os.getenv('MONGO_URI', 'mongodb://localhost:27017')
        self.client = motor.motor_asyncio.AsyncIOMotorClient(self.mongo_uri)
        self.db = self.client.discord_bot
        self.users = self.db.users
    
    async def get_user(self, user_id):
        user_data = await self.users.find_one({'_id': str(user_id)})
        if not user_data:
            # Create default user if not exists
            default_user = {
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
            await self.users.insert_one(default_user)
            return default_user
        return user_data
    
    async def update_user(self, user_id, update_data):
        await self.users.update_one(
            {'_id': str(user_id)},
            {'$set': update_data},
            upsert=True
        )
    
    async def increment_questions_answered(self, user_id):
        result = await self.users.update_one(
            {'_id': str(user_id)},
            {'$inc': {'questions_answered': 1}}
        )
        user_data = await self.get_user(user_id)
        return user_data.get('questions_answered', 0)
    
    async def add_premium_access(self, user_id, days):
        user_data = await self.get_user(user_id)
        
        if user_data.get('premium_until'):
            current_end = datetime.fromisoformat(user_data['premium_until'])
            new_end = current_end + timedelta(days=days)
        else:
            new_end = datetime.now() + timedelta(days=days)
        
        await self.users.update_one(
            {'_id': str(user_id)},
            {'$set': {
                'premium_until': new_end.isoformat(),
                'premium_access': True
            }}
        )
        return new_end
    
    async def set_admin(self, user_id, is_admin):
        await self.users.update_one(
            {'_id': str(user_id)},
            {'$set': {'is_admin': is_admin}}
        )
