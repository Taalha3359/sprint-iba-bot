import discord
from discord.ext import commands, tasks
from discord import app_commands
import asyncio
import os
import random
import json
from datetime import datetime, timedelta

import config
from utils.database import MongoDB  # Updated to MongoDB
from utils.question_manager import QuestionManager
from utils.access_control import AccessControl

# Setup bot
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix=config.BOT_PREFIX, intents=intents)

# Initialize components with MongoDB
db = MongoDB()
qm = QuestionManager()
access_control = AccessControl(db)

# Store active questions
active_questions = {}

# Background task for cleaning expired premium users
@tasks.loop(hours=24)
async def cleanup_expired_premium():
    """Daily cleanup of expired premium users"""
    try:
        count = await db.cleanup_expired_premium()
        if count > 0:
            print(f"Cleaned up {count} expired premium users")
    except Exception as e:
        print(f"Error in premium cleanup: {e}")

@cleanup_expired_premium.before_loop
async def before_cleanup():
    """Wait until bot is ready before starting cleanup task"""
    await bot.wait_until_ready()

@bot.event
async def on_ready():
    print(f'{bot.user} is now online!')
    
    # Initialize database indexes
    try:
        await db.ensure_indexes()
        print("✅ Database indexes initialized")
    except Exception as e:
        print(f"⚠️  Could not initialize database indexes: {e}")
    
    # Start background tasks
    cleanup_expired_premium.start()
    
    try:
        synced = await bot.tree.sync()
        print(f"Loaded {len(synced)} commands")
        
        # Print bot statistics
        stats = await db.get_user_stats()
        print(f"Bot Statistics: {stats['total_users']} users, {stats['premium_users']} premium, {stats['total_questions_answered']} questions answered")
        
    except Exception as e:
        print(f"Error: {e}")

async def send_question_response(interaction, question_data, subject, topic, user_id):
    """Helper function to send question responses with proper error handling"""
    # Determine time limit
    if subject == "math":
        time_limit = config.TIME_LIMITS['math']
    elif subject == "english":
        time_limit = config.TIME_LIMITS['english']
    elif subject == "analytical":
        time_limit = config.TIME_LIMITS['puzzle'] if topic == "puzzle" else config.TIME_LIMITS['analytical']
    else:
        time_limit = 60
    
    # Create embed
    embed = discord.Embed(
        title=f"{subject.capitalize()} - {topic}",
        description=f"**Question:**\n{question_data['question']}",
        color=discord.Color.blue() if subject == "math" else 
              discord.Color.green() if subject == "english" else 
              discord.Color.orange()
    )
    embed.set_footer(text=f"You have {time_limit} seconds")
    
    # Handle image
    file = None
    if question_data.get('image_path') and os.path.exists(question_data['image_path']):
        file = discord.File(question_data['image_path'], filename="question.png")
        embed.set_image(url="attachment://question.png")
    
    view = QuestionView(question_data, subject, topic, user_id, time_limit)
    
    # Send response - ensure we only respond once
    try:
        if interaction.response.is_done():
            # If interaction already responded, use followup
            if file:
                message = await interaction.followup.send(embed=embed, file=file, view=view, ephemeral=True, wait=True)
            else:
                message = await interaction.followup.send(embed=embed, view=view, ephemeral=True, wait=True)
        else:
            # Use initial response
            if file:
                await interaction.response.send_message(embed=embed, file=file, view=view, ephemeral=True)
                message = await interaction.original_response()
            else:
                await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
                message = await interaction.original_response()
        
        # Store message reference in the view
        view.message = message
        
        # Store active question
        active_questions[user_id] = {
            "question": question_data,
            "subject": subject,
            "topic": topic,
            "view": view,
            "message": message
        }
        
    except Exception as e:
        print(f"Error sending question: {e}")
        try:
            if not interaction.response.is_done():
                await interaction.response.send_message("An error occurred. Please try again.", ephemeral=True)
        except:
            try:
                await interaction.followup.send("An error occurred. Please try again.", ephemeral=True)
            except:
                pass

@bot.tree.command(name="math_practice", description="Practice math questions")
@app_commands.choices(topic=[app_commands.Choice(name=name, value=name) for name in config.MATH_TOPICS])
async def math_practice(interaction: discord.Interaction, topic: app_commands.Choice[str]):
    user_id = interaction.user.id
    
    # Check if user already has an active question
    if user_id in active_questions:
        try:
            await interaction.response.send_message("You already have an active question. Please answer it first.", ephemeral=True)
        except discord.errors.NotFound:
            await interaction.followup.send("You already have an active question. Please answer it first.", ephemeral=True)
        return
    
    # Check access
    has_access, access_type = await access_control.check_access(interaction)
    if not has_access:
        await access_control.send_access_denied_message(interaction, access_type)
        return
    
    # Get question
    question_data = qm.get_question("math", topic.value)
    if not question_data:
        try:
            await interaction.response.send_message(f"No questions found for {topic.value}", ephemeral=True)
        except discord.errors.NotFound:
            await interaction.followup.send(f"No questions found for {topic.value}", ephemeral=True)
        return
    
    await send_question_response(interaction, question_data, "math", topic.value, user_id)

@bot.tree.command(name="english_practice", description="Practice English questions")
@app_commands.choices(topic=[app_commands.Choice(name=name, value=name) for name in config.ENGLISH_TOPICS])
async def english_practice(interaction: discord.Interaction, topic: app_commands.Choice[str]):
    user_id = interaction.user.id
    
    # Check if user already has an active question
    if user_id in active_questions:
        try:
            await interaction.response.send_message("You already have an active question. Please answer it first.", ephemeral=True)
        except discord.errors.NotFound:
            await interaction.followup.send("You already have an active question. Please answer it first.", ephemeral=True)
        return
    
    # Check access
    has_access, access_type = await access_control.check_access(interaction)
    if not has_access:
        await access_control.send_access_denied_message(interaction, access_type)
        return
    
    # Get question
    question_data = qm.get_question("english", topic.value)
    if not question_data:
        try:
            await interaction.response.send_message(f"No questions found for {topic.value}", ephemeral=True)
        except discord.errors.NotFound:
            await interaction.followup.send(f"No questions found for {topic.value}", ephemeral=True)
        return
    
    await send_question_response(interaction, question_data, "english", topic.value, user_id)

@bot.tree.command(name="analytical_practice", description="Practice analytical questions")
@app_commands.choices(topic=[app_commands.Choice(name=name, value=name) for name in config.ANALYTICAL_TOPICS])
async def analytical_practice(interaction: discord.Interaction, topic: app_commands.Choice[str]):
    user_id = interaction.user.id
    
    # Check if user already has an active question
    if user_id in active_questions:
        try:
            await interaction.response.send_message("You already have an active question. Please answer it first.", ephemeral=True)
        except discord.errors.NotFound:
            await interaction.followup.send("You already have an active question. Please answer it first.", ephemeral=True)
        return
    
    # Check access
    has_access, access_type = await access_control.check_access(interaction)
    if not has_access:
        await access_control.send_access_denied_message(interaction, access_type)
        return
    
    # Get question
    question_data = qm.get_question("analytical", topic.value)
    if not question_data:
        try:
            await interaction.response.send_message(f"No questions found for {topic.value}", ephemeral=True)
        except discord.errors.NotFound:
            await interaction.followup.send(f"No questions found for {topic.value}", ephemeral=True)
        return
    
    await send_question_response(interaction, question_data, "analytical", topic.value, user_id)

# Leaderboard command
@bot.tree.command(name="leaderboard", description="Show leaderboard")
async def leaderboard(interaction: discord.Interaction):
    leaderboard_data = await db.get_leaderboard(10)
    
    embed = discord.Embed(
        title="Sprint IBA Leaderboard",
        description="Top performers",
        color=discord.Color.gold()
    )
    
    for i, (user_id, score) in enumerate(leaderboard_data[:10], 1):
        try:
            user = await bot.fetch_user(int(user_id))
            embed.add_field(name=f"{i}. {user.name}", value=f"Score: {score}", inline=False)
        except:
            embed.add_field(name=f"{i}. User {user_id}", value=f"Score: {score}", inline=False)
    
    if not leaderboard_data:
        embed.description = "No scores yet. Be the first to practice!"
    
    await interaction.response.send_message(embed=embed)

# Profile command
@bot.tree.command(name="profile", description="Check your stats")
async def profile(interaction: discord.Interaction):
    user_id = interaction.user.id
    user_data = await db.get_user(user_id)
    
    if not user_data:
        embed = discord.Embed(
            title=f"{interaction.user.name}'s Profile",
            description="Start practicing to see your stats!",
            color=discord.Color.blue()
        )
        await interaction.response.send_message(embed=embed)
        return
    
    embed = discord.Embed(
        title=f"{interaction.user.name}'s Profile",
        color=discord.Color.blue()
    )
    
    embed.add_field(name="Total Score", value=user_data.get('total_score', 0), inline=False)
    embed.add_field(name="Questions Answered", value=user_data.get('questions_answered', 0), inline=False)
    
    for subject in ['math', 'english', 'analytical']:
        if subject in user_data:
            correct = user_data[subject].get('correct', 0)
            total = user_data[subject].get('total', 0)
            accuracy = (correct / total * 100) if total > 0 else 0
            embed.add_field(
                name=subject.capitalize(),
                value=f"Accuracy: {accuracy:.1f}%\nCorrect: {correct}/{total}",
                inline=True
            )
    
    await interaction.response.send_message(embed=embed)

# In your main.py, update the QuestionView and QuestionButton classes:

class QuestionView(discord.ui.View):
    def __init__(self, question_data, subject, topic, user_id, timeout_duration):
        super().__init__(timeout=timeout_duration)
        self.question_data = question_data
        self.subject = subject
        self.topic = topic
        self.user_id = user_id
        self.message = None
        self.timed_out = False
        self.answered = False  # Track if question has been answered
        
        # Add buttons for options
        for i, option in enumerate(question_data['options']):
            self.add_item(QuestionButton(option, i, question_data['correct_answer'], self))
    
    async def on_timeout(self):
        if self.answered:
            return
            
        self.timed_out = True
        # Disable all buttons
        for item in self.children:
            if isinstance(item, discord.ui.Button):
                item.disabled = True
        
        # Update the message if it exists
        if self.message:
            try:
                await self.message.edit(view=self)
            except discord.NotFound:
                pass  # Message was already deleted
        
        # Handle timeout in database
        try:
            user_data = await db.get_user(self.user_id)
            subject_data = user_data.get(self.subject, {})
            subject_data['total'] = subject_data.get('total', 0) + 1
            subject_data['timeout'] = subject_data.get('timeout', 0) + 1
            user_data[self.subject] = subject_data
            await db.update_user(self.user_id, user_data)
        except Exception as e:
            print(f"Error handling timeout: {e}")
        
        # Remove from active questions
        if self.user_id in active_questions:
            del active_questions[self.user_id]

class QuestionButton(discord.ui.Button):
    def __init__(self, option, index, correct_index, parent_view):
        super().__init__(label=option, style=discord.ButtonStyle.secondary)
        self.index = index
        self.correct_index = correct_index
        self.parent_view = parent_view
    
    async def callback(self, interaction: discord.Interaction):
        # Only allow the original user to interact
        if interaction.user.id != self.parent_view.user_id:
            await interaction.response.send_message("This is not your question!", ephemeral=True)
            return
        
        # Prevent multiple answers
        if self.parent_view.answered:
            await interaction.response.send_message("You already answered this question!", ephemeral=True)
            return
        
        self.parent_view.answered = True
        
        # Disable all buttons
        for item in self.parent_view.children:
            if isinstance(item, discord.ui.Button):
                item.disabled = True
        
        try:
            # Update the message to show it's been answered
            await interaction.message.edit(view=self.parent_view)
        except discord.NotFound:
            pass  # Message was deleted
        
        # Process the answer
        try:
            user_data = await db.get_user(interaction.user.id)
            subject = self.parent_view.subject
            
            # Update question count
            await db.increment_questions_answered(interaction.user.id)
            
            subject_data = user_data.get(subject, {})
            subject_data['total'] = subject_data.get('total', 0) + 1
            
            is_correct = self.index == self.correct_index
            
            if is_correct:
                user_data['total_score'] = user_data.get('total_score', 0) + config.SCORING['correct']
                subject_data['correct'] = subject_data.get('correct', 0) + 1
                result_text = "Correct! ✅"
                color = discord.Color.green()
            else:
                user_data['total_score'] = user_data.get('total_score', 0) + config.SCORING['incorrect']
                result_text = f"Incorrect! ❌ Correct answer: {self.parent_view.question_data['options'][self.correct_index]}"
                color = discord.Color.red()
            
            user_data[subject] = subject_data
            await db.update_user(interaction.user.id, user_data)
            await db.update_leaderboard(interaction.user.id, user_data['total_score'])
            
            # Send result
            embed = discord.Embed(title=result_text, color=color)
            embed.add_field(name="Your Answer", value=self.label, inline=True)
            embed.add_field(name="Score", value=user_data['total_score'], inline=True)
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
            
        except Exception as e:
            print(f"Error processing answer: {e}")
            await interaction.response.send_message("An error occurred while processing your answer.", ephemeral=True)
        
        # Remove from active questions
        if interaction.user.id in active_questions:
            del active_questions[interaction.user.id]

@bot.tree.command(name="mystatus", description="Check your access status and remaining questions")
async def my_status(interaction: discord.Interaction):
    user_id = interaction.user.id
    user_data = await db.get_user(user_id)
    
    # Refresh premium status check
    premium_status = await db.check_premium_status(user_id)
    user_data['premium_access'] = premium_status
    
    embed = discord.Embed(title="Your Access Status", color=discord.Color.blue())
    
    # Premium status
    if user_data.get('premium_access') and user_data.get('premium_until'):
        try:
            premium_until = datetime.fromisoformat(user_data['premium_until'])
            embed.add_field(name="Premium Access", value=f"✅ Active until {premium_until.strftime('%Y-%m-%d %H:%M')}", inline=False)
        except:
            embed.add_field(name="Premium Access", value="✅ Active (invalid date format)", inline=False)
    else:
        embed.add_field(name="Premium Access", value="❌ No active subscription", inline=False)
    
    # Question usage
    questions_answered = user_data.get('questions_answered', 0)
    free_limit = config.PREMIUM_SETTINGS["free_question_limit"]
    remaining = max(0, free_limit - questions_answered)
    
    embed.add_field(
        name="Question Usage", 
        value=f"**Answered:** {questions_answered}\n**Remaining free:** {remaining}\n**Free limit:** {free_limit}", 
        inline=False
    )
    
    # Admin status
    if user_data.get('is_admin') or user_id in config.PREMIUM_SETTINGS["admin_ids"]:
        embed.add_field(name="Admin Status", value="✅ You have admin privileges", inline=False)
    
    await interaction.response.send_message(embed=embed, ephemeral=True)

# Admin commands group
admin_group = app_commands.Group(name="admin", description="Admin management commands")

@admin_group.command(name="add_ticket", description="Add premium access to a user")
@app_commands.choices(duration=[
    app_commands.Choice(name="7 Days", value="7days"),
    app_commands.Choice(name="14 Days", value="14days"),
    app_commands.Choice(name="1 Month", value="1month"),
    app_commands.Choice(name="3 Months", value="3months")
])
async def add_ticket(interaction: discord.Interaction, user: discord.User, duration: app_commands.Choice[str]):
    # Check if user is admin
    user_data = await db.get_user(interaction.user.id)
    if not user_data.get('is_admin') and interaction.user.id not in config.PREMIUM_SETTINGS["admin_ids"]:
        await interaction.response.send_message("❌ Admin access required.", ephemeral=True)
        return
    
    # Add premium access
    days = config.PREMIUM_SETTINGS["ticket_durations"][duration.value]
    premium_until = await db.add_premium_access(user.id, days)
    
    embed = discord.Embed(
        title="✅ Ticket Added",
        description=f"Premium access granted to {user.mention}\n"
                  f"**Duration:** {duration.name}\n"
                  f"**Expires:** {premium_until.strftime('%Y-%m-%d %H:%M')}",
        color=discord.Color.green()
    )
    
    await interaction.response.send_message(embed=embed)
    
    # Notify the user
    try:
        user_embed = discord.Embed(
            title="🎉 Premium Access Granted!",
            description=f"You've received {duration.name} of premium access!\n"
                      f"**Expires:** {premium_until.strftime('%Y-%m-%d %H:%M')}\n\n"
                      f"You can now use the bot without limits in our premium channel.",
            color=discord.Color.gold()
        )
        await user.send(embed=user_embed)
    except:
        pass  # Can't DM user

@admin_group.command(name="check_access", description="Check a user's access status")
async def check_access(interaction: discord.Interaction, user: discord.User):
    user_data = await db.get_user(user.id)
    
    embed = discord.Embed(title=f"Access Status: {user.display_name}", color=discord.Color.blue())
    
    # Premium status
    if user_data.get('premium_access'):
        premium_until = datetime.fromisoformat(user_data['premium_until'])
        embed.add_field(name="Premium Status", value=f"✅ Active until {premium_until.strftime('%Y-%m-%d')}", inline=False)
    else:
        embed.add_field(name="Premium Status", value="❌ No active subscription", inline=False)
    
    # Question usage
    questions_answered = user_data.get('questions_answered', 0)
    free_limit = config.PREMIUM_SETTINGS["free_question_limit"]
    remaining = max(0, free_limit - questions_answered)
    embed.add_field(name="Question Usage", value=f"**Answered:** {questions_answered}\n**Remaining free:** {remaining}", inline=False)
    
    # Admin status
    if user_data.get('is_admin') or user.id in config.PREMIUM_SETTINGS["admin_ids"]:
        embed.add_field(name="Admin", value="✅ Yes", inline=True)
    else:
        embed.add_field(name="Admin", value="❌ No", inline=True)
    
    await interaction.response.send_message(embed=embed, ephemeral=True)

@admin_group.command(name="stats", description="Get bot statistics")
async def admin_stats(interaction: discord.Interaction):
    # Check if user is admin
    user_data = await db.get_user(interaction.user.id)
    if not user_data.get('is_admin') and interaction.user.id not in config.PREMIUM_SETTINGS["admin_ids"]:
        await interaction.response.send_message("❌ Admin access required.", ephemeral=True)
        return
    
    stats = await db.get_user_stats()
    
    embed = discord.Embed(
        title="Bot Statistics",
        description="Overall bot usage statistics",
        color=discord.Color.purple()
    )
    
    embed.add_field(name="Total Users", value=stats['total_users'], inline=True)
    embed.add_field(name="Premium Users", value=stats['premium_users'], inline=True)
    embed.add_field(name="Questions Answered", value=stats['total_questions_answered'], inline=True)
    
    await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(name="debug_questions", description="Debug question counter")
async def debug_questions(interaction: discord.Interaction):
    if interaction.user.id not in config.PREMIUM_SETTINGS["admin_ids"]:
        await interaction.response.send_message("❌ Admin only command.", ephemeral=True)
        return
    
    user_id = interaction.user.id
    user_data = await db.get_user(user_id)
    
    debug_info = f"""
    User ID: {user_id}
    questions_answered: {user_data.get('questions_answered', 0)}
    Raw data: {user_data}
    """
    
    await interaction.response.send_message(f"```{debug_info}```", ephemeral=True)

# Register admin commands
bot.tree.add_command(admin_group)

# Error handling
@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound):
        return
    print(f"Error: {error}")

@bot.event
async def on_app_command_error(interaction, error):
    print(f"App Command Error: {error}")
    try:
        await interaction.response.send_message("An error occurred. Please try again.", ephemeral=True)
    except:
        pass

# Run the bot
if __name__ == "__main__":
    bot.run(config.BOT_TOKEN)


