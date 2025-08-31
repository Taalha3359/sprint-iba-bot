import os
from pymongo import MongoClient

class Leaderboard:
    def __init__(self):
        self.connection_string = os.getenv('MONGODB_URI')
        if not self.connection_string:
            raise ValueError("MONGODB_URI environment variable is not set")
        
        self.client = MongoClient(self.connection_string)
        self.db = self.client.sprint_bot
        self.users = self.db.users
    
    def update_score(self, user_id, score):
        try:
            self.users.update_one(
                {'_id': str(user_id)},
                {'$set': {'total_score': score}},
                upsert=True
            )
        except Exception as e:
            print(f"Error updating leaderboard score: {e}")
    
    def get_leaderboard(self):
        try:
            # Get top 10 users by score
            top_users = self.users.find().sort('total_score', -1).limit(10)
            
            leaderboard_data = []
            for user in top_users:
                if 'total_score' in user:
                    leaderboard_data.append((user['_id'], user['total_score']))
            
            return leaderboard_data
        except Exception as e:
            print(f"Error getting leaderboard: {e}")
            return []
