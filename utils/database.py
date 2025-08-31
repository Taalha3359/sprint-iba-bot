import motor.motor_asyncio
from datetime import datetime, timedelta
import os
from bson import ObjectId
import json
import asyncio

class MongoDB:
    def __init__(self):
        self.mongo_uri = os.getenv('MONGO_URI', 'mongodb://localhost:27017/discord_bot')
        self.client = motor.motor_asyncio.AsyncIOMotorClient(self.mongo_uri)
        # Extract database name from URI or use default
        if '/' in self.mongo_uri:
            db_name = self.mongo_uri.split('/')[-1].split('?')[0]
        else:
            db_name = 'discord_bot'
        self.db = self.client[db_name]
        self.users = self.db.users
        self.leaderboard = self.db.leaderboard
        
        # Create indexes in the background
        asyncio.create_task(self._create_indexes())
    
    async def _create_indexes(self):
        """Create indexes for better query performance"""
        try:
            # Try to create indexes, but don't fail if we don't have permissions
            try:
                await self.users.create_index("_id")
                await self.users.create_index("premium_until")
                await self.users.create_index("is_admin")
                await self.leaderboard.create_index("_id")
                print("✅ Database indexes created successfully")
            except Exception as e:
                # If we can't create indexes (due to auth), just continue
                print(f"⚠️  Could not create indexes (may need admin permissions): {e}")
        except Exception as e:
            print(f"❌ Error in index creation: {e}")
    
    async def get_user(self, user_id):
        """Get user data from MongoDB"""
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
                'analytical': {'correct': 0, 'total': 0, 'topics': {}},
                'created_at': datetime.now().isoformat(),
                'last_updated': datetime.now().isoformat()
            }
            await self.users.insert_one(default_user)
            return default_user
        return user_data
    
    async def update_user(self, user_id, update_data):
        """Update user data in MongoDB"""
        update_data['last_updated'] = datetime.now().isoformat()
        await self.users.update_one(
            {'_id': str(user_id)},
            {'$set': update_data},
            upsert=True
        )
    
    async def increment_questions_answered(self, user_id):
        """Increment questions answered counter"""
        result = await self.users.update_one(
            {'_id': str(user_id)},
            {'$inc': {'questions_answered': 1}},
            upsert=True
        )
        user_data = await self.get_user(user_id)
        return user_data.get('questions_answered', 0)
    
    async def add_premium_access(self, user_id, days):
        """Add premium access to a user"""
        user_data = await self.get_user(user_id)
        
        if user_data.get('premium_until'):
            try:
                current_end = datetime.fromisoformat(user_data['premium_until'])
                new_end = current_end + timedelta(days=days)
            except (ValueError, TypeError):
                new_end = datetime.now() + timedelta(days=days)
        else:
            new_end = datetime.now() + timedelta(days=days)
        
        await self.users.update_one(
            {'_id': str(user_id)},
            {'$set': {
                'premium_until': new_end.isoformat(),
                'premium_access': True,
                'last_updated': datetime.now().isoformat()
            }},
            upsert=True
        )
        return new_end
    
    async def check_premium_status(self, user_id):
        """Check and update premium status"""
        user_data = await self.get_user(user_id)
        if user_data.get('premium_until'):
            try:
                premium_until = datetime.fromisoformat(user_data['premium_until'])
                if datetime.now() > premium_until:
                    await self.users.update_one(
                        {'_id': str(user_id)},
                        {'$set': {
                            'premium_access': False,
                            'premium_until': None,
                            'last_updated': datetime.now().isoformat()
                        }}
                    )
                    return False
                return True
            except (ValueError, TypeError):
                await self.users.update_one(
                    {'_id': str(user_id)},
                    {'$set': {
                        'premium_access': False,
                        'premium_until': None,
                        'last_updated': datetime.now().isoformat()
                    }}
                )
                return False
        return False
    
    async def set_admin(self, user_id, is_admin):
        """Set admin status for a user"""
        await self.users.update_one(
            {'_id': str(user_id)},
            {'$set': {
                'is_admin': is_admin,
                'last_updated': datetime.now().isoformat()
            }},
            upsert=True
        )
    
    async def update_leaderboard(self, user_id, score):
        """Update leaderboard score"""
        await self.leaderboard.update_one(
            {'_id': str(user_id)},
            {'$set': {'score': score}},
            upsert=True
        )
    
    async def get_leaderboard(self, limit=10):
        """Get leaderboard data"""
        cursor = self.leaderboard.find().sort('score', -1).limit(limit)
        leaderboard_data = []
        async for document in cursor:
            leaderboard_data.append((document['_id'], document.get('score', 0)))
        return leaderboard_data
    
    async def bulk_update_users(self, updates):
        """Bulk update multiple users for efficiency"""
        if not updates:
            return
        
        bulk_operations = []
        for user_id, update_data in updates.items():
            update_data['last_updated'] = datetime.now().isoformat()
            bulk_operations.append(
                motor.motor_asyncio.UpdateOne(
                    {'_id': str(user_id)},
                    {'$set': update_data},
                    upsert=True
                )
            )
        
        if bulk_operations:
            await self.users.bulk_write(bulk_operations)
    
    async def get_all_premium_users(self):
        """Get all premium users for maintenance tasks"""
        cursor = self.users.find({
            'premium_access': True,
            'premium_until': {'$ne': None}
        })
        
        premium_users = []
        async for document in cursor:
            premium_users.append(document)
        return premium_users
    
    async def cleanup_expired_premium(self):
        """Clean up expired premium users"""
        current_time = datetime.now().isoformat()
        
        # Find users with expired premium
        cursor = self.users.find({
            'premium_access': True,
            'premium_until': {'$lt': current_time}
        })
        
        updates = {}
        async for document in cursor:
            user_id = document['_id']
            updates[user_id] = {
                'premium_access': False,
                'premium_until': None
            }
        
        await self.bulk_update_users(updates)
        return len(updates)
    
    async def get_user_stats(self):
        """Get overall bot statistics"""
        total_users = await self.users.count_documents({})
        premium_users = await self.users.count_documents({'premium_access': True})
        total_questions = await self.users.aggregate([
            {'$group': {'_id': None, 'total': {'$sum': '$questions_answered'}}}
        ]).to_list(length=1)
        
        total_questions = total_questions[0]['total'] if total_questions else 0
        
        return {
            'total_users': total_users,
            'premium_users': premium_users,
            'total_questions_answered': total_questions
        }

# For backward compatibility
class UserDatabase(MongoDB):
    """Legacy class name for backward compatibility"""
    pass

# Async helper functions
import asyncio

async def test_connection():
    """Test MongoDB connection"""
    db = MongoDB()
    try:
        # Test connection
        await db.client.admin.command('ping')
        print("✅ MongoDB connection successful")
        
        # Test basic operations
        test_user_id = "test_user_123"
        user_data = await db.get_user(test_user_id)
        print(f"✅ User retrieval test passed: {user_data['_id']}")
        
        await db.update_user(test_user_id, {'test_field': 'test_value'})
        print("✅ User update test passed")
        
        await db.increment_questions_answered(test_user_id)
        print("✅ Question increment test passed")
        
        # Clean up test data
        await db.users.delete_one({'_id': test_user_id})
        print("✅ Test cleanup completed")
        
    except Exception as e:
        print(f"❌ MongoDB connection failed: {e}")

if __name__ == "__main__":
    # Run connection test
    asyncio.run(test_connection())


