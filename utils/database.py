import motor.motor_asyncio
from datetime import datetime
import os

class MongoDB:
    def __init__(self):
        self.mongo_uri = os.getenv('MONGO_URI', 'mongodb://localhost:27017/discord_bot')
        self.client = motor.motor_asyncio.AsyncIOMotorClient(self.mongo_uri)
        self.db = self.client.get_database()
        self.users = self.db.users
        self.leaderboard = self.db.leaderboard
    
    async def get_user(self, user_id):
        user_data = await self.users.find_one({'_id': str(user_id)})
        if not user_data:
            user_data = {
                '_id': str(user_id),
                'total_score': 0,
                'questions_answered': 0
            }
            await self.users.insert_one(user_data)
        return user_data
    
    async def update_user(self, user_id, update_data):
        await self.users.update_one(
            {'_id': str(user_id)},
            {'$set': update_data},
            upsert=True
        )
    
    async def update_leaderboard(self, user_id, score):
        await self.leaderboard.update_one(
            {'_id': str(user_id)},
            {'$set': {'score': score}},
            upsert=True
        )
    
    async def get_leaderboard(self, limit=10):
        cursor = self.leaderboard.find().sort('score', -1).limit(limit)
        leaderboard_data = []
        async for document in cursor:
            leaderboard_data.append((document['_id'], document.get('score', 0)))
        return leaderboard_data
