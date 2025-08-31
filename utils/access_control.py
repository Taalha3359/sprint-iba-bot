import discord
from datetime import datetime
import config
import asyncio
from typing import Tuple, Optional

class AccessControl:
    def __init__(self, database):
        self.db = database
        self.user_cache = {}  # Cache for user access data
        self.cache_lock = asyncio.Lock()
    
    async def _get_cached_user_data(self, user_id: int) -> Optional[dict]:
        """Get user data from cache if available and not expired"""
        async with self.cache_lock:
            cached_data = self.user_cache.get(user_id)
            if cached_data and (datetime.now() - cached_data['timestamp']).total_seconds() < config.CACHE_SETTINGS["user_cache_ttl"]:
                return cached_data['data']
        return None
    
    async def _set_cached_user_data(self, user_id: int, user_data: dict):
        """Store user data in cache"""
        async with self.cache_lock:
            self.user_cache[user_id] = {
                'data': user_data,
                'timestamp': datetime.now()
            }
            # Clean up cache if it exceeds maximum size
            if len(self.user_cache) > config.CACHE_SETTINGS["max_cached_users"]:
                # Remove oldest entries
                sorted_entries = sorted(self.user_cache.items(), key=lambda x: x[1]['timestamp'])
                for user_id_to_remove, _ in sorted_entries[:len(self.user_cache) - config.CACHE_SETTINGS["max_cached_users"]]:
                    del self.user_cache[user_id_to_remove]
    
    async def _clear_user_cache(self, user_id: int):
        """Clear cached data for a specific user"""
        async with self.cache_lock:
            if user_id in self.user_cache:
                del self.user_cache[user_id]
    
    async def check_access(self, interaction: discord.Interaction) -> Tuple[bool, str]:
        """Check if user has access to use the bot in the current channel"""
        user_id = interaction.user.id
        channel_id = interaction.channel_id
        
        # Check if user is admin (bypass all restrictions)
        if await self._is_admin(user_id):
            return True, "admin"
        
        # Check premium channel access
        if channel_id == config.PREMIUM_SETTINGS["premium_channel_id"]:
            # Check if user has active premium
            if await self._check_premium_status(user_id):
                return True, "premium_channel"
            else:
                return False, "no_premium_in_channel"
        
        # Regular channel - check question limit
        questions_answered = await self._get_questions_answered(user_id)
        if questions_answered < config.PREMIUM_SETTINGS["free_question_limit"]:
            return True, "free_access"
        else:
            return False, "limit_reached"
    
    async def _is_admin(self, user_id: int) -> bool:
        """Check if user is an admin"""
        # First check config admin IDs (fast, no DB query)
        if user_id in config.PREMIUM_SETTINGS["admin_ids"]:
            return True
        
        # Check database for admin status
        user_data = await self._get_user_data(user_id)
        return user_data.get('is_admin', False)
    
    async def _get_user_data(self, user_id: int) -> dict:
        """Get user data with caching"""
        # Try to get from cache first
        cached_data = await self._get_cached_user_data(user_id)
        if cached_data:
            return cached_data
        
        # Get from database
        user_data = await self.db.get_user(user_id)
        
        # Cache the result
        await self._set_cached_user_data(user_id, user_data)
        
        return user_data
    
    async def _get_questions_answered(self, user_id: int) -> int:
        """Get number of questions answered by user"""
        user_data = await self._get_user_data(user_id)
        return user_data.get('questions_answered', 0)
    
    async def _check_premium_status(self, user_id: int) -> bool:
        """Check and update premium status for a user"""
        user_data = await self._get_user_data(user_id)
        
        # Check Discord roles for premium access
        if await self._check_premium_roles(user_id):
            return True
        
        if user_data.get('premium_until'):
            try:
                premium_until = datetime.fromisoformat(user_data['premium_until'])
                if datetime.now() > premium_until:
                    # Premium expired, update database
                    updated_data = {
                        'premium_access': False,
                        'premium_until': None
                    }
                    await self.db.update_user(user_id, updated_data)
                    await self._clear_user_cache(user_id)  # Clear cache
                    return False
                return True
            except (ValueError, TypeError):
                # Invalid date format, remove premium
                updated_data = {
                    'premium_access': False,
                    'premium_until': None
                }
                await self.db.update_user(user_id, updated_data)
                await self._clear_user_cache(user_id)  # Clear cache
                return False
        return False
    
    async def _check_premium_roles(self, user_id: int) -> bool:
        """Check if user has premium roles (for future Discord role integration)"""
        # This method can be extended to check Discord roles
        # For now, it's a placeholder for future functionality
        return False
    
    async def get_remaining_questions(self, user_id: int) -> int:
        """Get remaining free questions for a user"""
        questions_answered = await self._get_questions_answered(user_id)
        free_limit = config.PREMIUM_SETTINGS["free_question_limit"]
        return max(0, free_limit - questions_answered)
    
    async def get_user_access_info(self, user_id: int) -> dict:
        """Get comprehensive access information for a user"""
        user_data = await self._get_user_data(user_id)
        questions_answered = user_data.get('questions_answered', 0)
        free_limit = config.PREMIUM_SETTINGS["free_question_limit"]
        remaining = max(0, free_limit - questions_answered)
        
        premium_status = await self._check_premium_status(user_id)
        premium_until = user_data.get('premium_until')
        is_admin = await self._is_admin(user_id)
        
        return {
            'is_admin': is_admin,
            'premium_access': premium_status,
            'premium_until': premium_until,
            'questions_answered': questions_answered,
            'remaining_questions': remaining,
            'free_limit': free_limit,
            'has_unlimited_access': premium_status or is_admin
        }
    
    async def send_access_denied_message(self, interaction: discord.Interaction, access_type: str):
        """Send appropriate access denied message based on denial type"""
        user_id = interaction.user.id
        user_info = await self.get_user_access_info(user_id)
        
        if access_type == "no_premium_in_channel":
            embed = discord.Embed(
                title="🚫 Premium Access Required",
                description="This channel requires premium access to use the bot.\n\n"
                          f"Please ask an admin for a ticket to access premium features.",
                color=config.get_embed_color("error")
            )
            
            # Add user's current status
            if user_info['premium_access'] and user_info['premium_until']:
                try:
                    premium_until = datetime.fromisoformat(user_info['premium_until'])
                    embed.add_field(
                        name="Your Premium Status",
                        value=f"✅ Active until {premium_until.strftime('%Y-%m-%d %H:%M')}",
                        inline=False
                    )
                except:
                    embed.add_field(
                        name="Your Premium Status",
                        value="❌ Invalid premium data",
                        inline=False
                    )
            else:
                embed.add_field(
                    name="Your Premium Status",
                    value="❌ No active premium subscription",
                    inline=False
                )
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
        
        elif access_type == "limit_reached":
            embed = discord.Embed(
                title="🎯 Free Limit Reached",
                description=f"You've used all {config.PREMIUM_SETTINGS['free_question_limit']} free questions!\n\n"
                          f"**To continue practicing:**\n"
                          f"• Join our premium channel for unlimited access\n"
                          f"• Ask an admin for a trial ticket",
                color=config.get_embed_color("warning")
            )
            
            # Add usage statistics
            embed.add_field(
                name="Your Usage",
                value=f"**Questions answered:** {user_info['questions_answered']}\n"
                      f"**Free limit:** {user_info['free_limit']}\n"
                      f"**Remaining questions:** {user_info['remaining_questions']}",
                inline=False
            )
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
        
        return False
    
    async def can_bypass_rate_limit(self, user_id: int) -> bool:
        """Check if user can bypass rate limits (admins and premium users)"""
        if await self._is_admin(user_id):
            return True
        
        if await self._check_premium_status(user_id):
            return True
        
        return False
    
    async def get_rate_limit_multiplier(self, user_id: int) -> float:
        """Get rate limit multiplier for user (lower = less restrictive)"""
        if await self._is_admin(user_id):
            return 0.1  # Admins have very relaxed rate limits
        
        if await self._check_premium_status(user_id):
            return config.RATE_LIMIT_SETTINGS["premium_cooldown_multiplier"]
        
        return 1.0  # Regular users have standard rate limits
    
    async def refresh_user_cache(self, user_id: int):
        """Force refresh of cached user data"""
        await self._clear_user_cache(user_id)
        await self._get_user_data(user_id)  # This will fetch fresh data and cache it
    
    async def bulk_refresh_cache(self, user_ids: list):
        """Refresh cache for multiple users"""
        for user_id in user_ids:
            await self.refresh_user_cache(user_id)
    
    async def clear_all_cache(self):
        """Clear all cached user data"""
        async with self.cache_lock:
            self.user_cache.clear()

# Rate limiting decorator for future use
def rate_limit(access_control: AccessControl):
    """Decorator to add rate limiting to commands"""
    def decorator(func):
        async def wrapper(interaction: discord.Interaction, *args, **kwargs):
            user_id = interaction.user.id
            
            # Check if user can bypass rate limits
            if await access_control.can_bypass_rate_limit(user_id):
                return await func(interaction, *args, **kwargs)
            
            # TODO: Implement rate limiting logic here
            # For now, just pass through
            return await func(interaction, *args, **kwargs)
        
        return wrapper
    return decorator

# Access control check decorator
def requires_access(access_control: AccessControl):
    """Decorator to check access before executing command"""
    def decorator(func):
        async def wrapper(interaction: discord.Interaction, *args, **kwargs):
            has_access, access_type = await access_control.check_access(interaction)
            
            if not has_access:
                await access_control.send_access_denied_message(interaction, access_type)
                return
            
            return await func(interaction, *args, **kwargs)
        
        return wrapper
    return decorator

# Admin-only decorator
def admin_only(access_control: AccessControl):
    """Decorator to restrict command to admins only"""
    def decorator(func):
        async def wrapper(interaction: discord.Interaction, *args, **kwargs):
            user_id = interaction.user.id
            
            if not await access_control._is_admin(user_id):
                embed = discord.Embed(
                    title="❌ Access Denied",
                    description="This command is restricted to administrators only.",
                    color=config.get_embed_color("error")
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return
            
            return await func(interaction, *args, **kwargs)
        
        return wrapper
    return decorator

# Premium-only decorator
def premium_only(access_control: AccessControl):
    """Decorator to restrict command to premium users only"""
    def decorator(func):
        async def wrapper(interaction: discord.Interaction, *args, **kwargs):
            user_id = interaction.user.id
            
            if not await access_control._check_premium_status(user_id) and not await access_control._is_admin(user_id):
                embed = discord.Embed(
                    title="❌ Premium Required",
                    description="This command requires a premium subscription.",
                    color=config.get_embed_color("error")
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return
            
            return await func(interaction, *args, **kwargs)
        
        return wrapper
    return decorator
