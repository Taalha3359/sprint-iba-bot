import discord
from datetime import datetime
import config

class AccessControl:
    def __init__(self, database):
        self.db = database
    
    async def check_access(self, interaction: discord.Interaction):
        user_id = interaction.user.id
        channel_id = interaction.channel_id
        
        # Check if user is admin
        user_data = self.db.get_user(user_id)
        if user_data.get('is_admin') or user_id in config.PREMIUM_SETTINGS["admin_ids"]:
            return True, "admin"
        
        # Check premium channel access
        if channel_id == config.PREMIUM_SETTINGS["premium_channel_id"]:
            # Check if user has active premium
            if self.db.check_premium_status(user_id):
                return True, "premium_channel"
            else:
                return False, "no_premium_in_channel"
        
        # Regular channel - check question limit
        questions_answered = user_data.get('questions_answered', 0)
        if questions_answered < config.PREMIUM_SETTINGS["free_question_limit"]:
            return True, "free_access"
        else:
            return False, "limit_reached"
    
    def get_remaining_questions(self, user_id):
        user_data = self.db.get_user(user_id)
        questions_answered = user_data.get('questions_answered', 0)
        free_limit = config.PREMIUM_SETTINGS["free_question_limit"]
        return max(0, free_limit - questions_answered)
    
    async def send_access_denied_message(self, interaction, access_type):
        if access_type == "no_premium_in_channel":
            embed = discord.Embed(
                title="🚫 Premium Access Required",
                description="This channel requires premium access to use the bot.\n\n"
                          f"Please purchase a ticket from an admin to access premium features.",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
        
        elif access_type == "limit_reached":
            embed = discord.Embed(
                title="🎯 Free Limit Reached",
                description=f"You've used all {config.PREMIUM_SETTINGS['free_question_limit']} free questions!\n\n"
                          f"**To continue practicing:**\n"
                          f"• Join our premium channel for unlimited access\n"
                          f"• Ask an admin for a trial ticket\n"
                          f"• Wait for your monthly limit reset",
                color=discord.Color.orange()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
        
        return False
