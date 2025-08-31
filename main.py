import discord
from discord.ext import commands
from discord import app_commands
import asyncio
import os
import random
import json
from datetime import datetime, timedelta

import config
from utils.database import UserDatabase
from utils.question_manager import QuestionManager
from utils.leaderboard import Leaderboard
from utils.access_control import AccessControl
from pymongo import MongoClient

# Your connection string from GitHub Secrets
MONGODB_URI = os.getenv('MONGODB_URI')

# Connect to MongoDB
client = MongoClient(MONGODB_URI)
db = client.sprint_bot  # Your database name
users = db.users        # Your collection name

# Setup bot
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix=config.BOT_PREFIX, intents=intents)

# Initialize components
db = UserDatabase()
qm = QuestionManager()
lb = Leaderboard()
access_control = AccessControl(db)

# Store active questions
active_questions = {}

# Admin commands group
admin_group = app_commands.Group(name="admin", description="Admin management commands")

@bot.event
async def on_ready():
    print(f'{bot.user} is now online!')
    
    # Check for expired premium access
    data = db._read_data()
    for user_id, user_data in data.items():
        if user_data.get('premium_until'):
            premium_until = datetime.fromisoformat(user_data['premium_until'])
            if datetime.now() > premium_until:
                user_data['premium_access'] = False
                user_data['premium_until'] = None
                db.update_user(user_id, user_data)
                print(f"Expired premium access for user {user_id}")
    
    try:
        # Sync commands globally
        synced = await bot.tree.sync()
        print(f"✅ Loaded {len(synced)} commands")
        
        # Debug: List all commands
        commands = await bot.tree.fetch_commands()
        for cmd in commands:
            print(f"Command: /{cmd.name}")
            
    except Exception as e:
        print(f"❌ Error syncing commands: {e}")
        import traceback
        traceback.print_exc()

@bot.tree.command(name="math_practice", description="Practice math questions")
@app_commands.choices(topic=[app_commands.Choice(name=name, value=name) for name in config.MATH_TOPICS])
async def math_practice(interaction: discord.Interaction, topic: app_commands.Choice[str]):
    try:
        user_id = interaction.user.id
        
        # Check if user already has an active question
        if user_id in active_questions:
            try:
                await interaction.response.send_message("You already have an active question. Please answer it first.", ephemeral=True)
            except discord.errors.NotFound:
                # Interaction already expired, use followup
                await interaction.followup.send("You already have an active question. Please answer it first.", ephemeral=True)
            return
        
        # Check access
        access_control = AccessControl(db)
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
        
        # Create embed
        embed = discord.Embed(
            title=f"Math - {topic.value}",
            description=f"**Question:**\n{question_data['question']}",
            color=discord.Color.blue()
        )
        embed.set_footer(text=f"You have {config.TIME_LIMITS['math']} seconds")
        
        # Handle image
        file = None
        if question_data.get('image_path') and os.path.exists(question_data['image_path']):
            file = discord.File(question_data['image_path'], filename="question.png")
            embed.set_image(url="attachment://question.png")
        
        view = QuestionView(question_data, "math", user_id)
        
        # Send response with error handling
        try:
            if file:
                await interaction.response.send_message(embed=embed, file=file, view=view, ephemeral=True)
            else:
                await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
            
            # Store active question if response was successful
            active_questions[user_id] = {
                "question": question_data,
                "subject": "math",
                "topic": topic.value,
                "message": await interaction.original_response(),
                "timeout": asyncio.create_task(question_timeout(user_id, config.TIME_LIMITS['math']))
            }
            
        except discord.errors.NotFound:
            # Interaction expired, send as followup instead
            if file:
                await interaction.followup.send(embed=embed, file=file, view=view, ephemeral=True)
            else:
                await interaction.followup.send(embed=embed, view=view, ephemeral=True)
            
            # For followup, we can't get original_response(), so handle differently
            active_questions[user_id] = {
                "question": question_data,
                "subject": "math",
                "topic": topic.value,
                "message": None,  # Can't store message reference for followup
                "timeout": asyncio.create_task(question_timeout(user_id, config.TIME_LIMITS['math']))
            }
            
    except Exception as e:
        print(f"Error in math_practice: {e}")
        # Try to send error message if possible
        try:
            await interaction.response.send_message("An error occurred. Please try again.", ephemeral=True)
        except discord.errors.NotFound:
            try:
                await interaction.followup.send("An error occurred. Please try again.", ephemeral=True)
            except:
                pass  # Give up if both fail

@bot.tree.command(name="english_practice", description="Practice English questions")
@app_commands.choices(topic=[app_commands.Choice(name=name, value=name) for name in config.ENGLISH_TOPICS])
async def english_practice(interaction: discord.Interaction, topic: app_commands.Choice[str]):
    try:
        user_id = interaction.user.id
        
        # Check if user already has an active question
        if user_id in active_questions:
            try:
                await interaction.response.send_message("You already have an active question. Please answer it first.", ephemeral=True)
            except discord.errors.NotFound:
                await interaction.followup.send("You already have an active question. Please answer it first.", ephemeral=True)
            return
        
        # Check access
        access_control = AccessControl(db)
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
        
        # Create embed
        embed = discord.Embed(
            title=f"English - {topic.value}",
            description=f"**Question:**\n{question_data['question']}",
            color=discord.Color.green()
        )
        embed.set_footer(text=f"You have {config.TIME_LIMITS['english']} seconds")
        
        # Handle image
        file = None
        if question_data.get('image_path') and os.path.exists(question_data['image_path']):
            file = discord.File(question_data['image_path'], filename="question.png")
            embed.set_image(url="attachment://question.png")
        
        view = QuestionView(question_data, "english", user_id)
        
        # Send response with error handling
        try:
            if file:
                await interaction.response.send_message(embed=embed, file=file, view=view, ephemeral=True)
            else:
                await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
            
            # Store active question if response was successful
            active_questions[user_id] = {
                "question": question_data,
                "subject": "english",
                "topic": topic.value,
                "message": await interaction.original_response(),
                "timeout": asyncio.create_task(question_timeout(user_id, config.TIME_LIMITS['english']))
            }
            
        except discord.errors.NotFound:
            # Interaction expired, send as followup instead
            if file:
                await interaction.followup.send(embed=embed, file=file, view=view, ephemeral=True)
            else:
                await interaction.followup.send(embed=embed, view=view, ephemeral=True)
            
            # For followup, we can't get original_response(), so handle differently
            active_questions[user_id] = {
                "question": question_data,
                "subject": "english",
                "topic": topic.value,
                "message": None,
                "timeout": asyncio.create_task(question_timeout(user_id, config.TIME_LIMITS['english']))
            }
            
    except Exception as e:
        print(f"Error in english_practice: {e}")
        try:
            await interaction.response.send_message("An error occurred. Please try again.", ephemeral=True)
        except discord.errors.NotFound:
            try:
                await interaction.followup.send("An error occurred. Please try again.", ephemeral=True)
            except:
                pass

@bot.tree.command(name="analytical_practice", description="Practice analytical questions")
@app_commands.choices(topic=[app_commands.Choice(name=name, value=name) for name in config.ANALYTICAL_TOPICS])
async def analytical_practice(interaction: discord.Interaction, topic: app_commands.Choice[str]):
    try:
        user_id = interaction.user.id
        
        # Check if user already has an active question
        if user_id in active_questions:
            try:
                await interaction.response.send_message("You already have an active question. Please answer it first.", ephemeral=True)
            except discord.errors.NotFound:
                await interaction.followup.send("You already have an active question. Please answer it first.", ephemeral=True)
            return
        
        # Check access
        access_control = AccessControl(db)
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
        
        # Determine time limit based on topic
        if topic.value == "puzzle":
            time_limit = config.TIME_LIMITS['puzzle']
        else:
            time_limit = config.TIME_LIMITS['analytical']
        
        # Create embed
        embed = discord.Embed(
            title=f"Analytical - {topic.value}",
            description=f"**Question:**\n{question_data['question']}",
            color=discord.Color.orange()
        )
        embed.set_footer(text=f"You have {time_limit} seconds")
        
        # Handle image
        file = None
        if question_data.get('image_path') and os.path.exists(question_data['image_path']):
            file = discord.File(question_data['image_path'], filename="question.png")
            embed.set_image(url="attachment://question.png")
        
        view = QuestionView(question_data, "analytical", user_id)
        
        # Send response with error handling
        try:
            if file:
                await interaction.response.send_message(embed=embed, file=file, view=view, ephemeral=True)
            else:
                await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
            
            # Store active question if response was successful
            active_questions[user_id] = {
                "question": question_data,
                "subject": "analytical",
                "topic": topic.value,
                "message": await interaction.original_response(),
                "timeout": asyncio.create_task(question_timeout(user_id, time_limit))
            }
            
        except discord.errors.NotFound:
            # Interaction expired, send as followup instead
            if file:
                await interaction.followup.send(embed=embed, file=file, view=view, ephemeral=True)
            else:
                await interaction.followup.send(embed=embed, view=view, ephemeral=True)
            
            # For followup, we can't get original_response(), so handle differently
            active_questions[user_id] = {
                "question": question_data,
                "subject": "analytical",
                "topic": topic.value,
                "message": None,
                "timeout": asyncio.create_task(question_timeout(user_id, time_limit))
            }
            
    except Exception as e:
        print(f"Error in analytical_practice: {e}")
        try:
            await interaction.response.send_message("An error occurred. Please try again.", ephemeral=True)
        except discord.errors.NotFound:
            try:
                await interaction.followup.send("An error occurred. Please try again.", ephemeral=True)
            except:
                pass


# Leaderboard command
@bot.tree.command(name="leaderboard", description="Show leaderboard")
async def leaderboard(interaction: discord.Interaction):
    leaderboard_data = lb.get_leaderboard()
    
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
    user_data = db.get_user(user_id)
    
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

class QuestionView(discord.ui.View):
    def __init__(self, question_data, subject, user_id):
        # Set timeout based on subject
        if subject == "math":
            timeout = config.TIME_LIMITS['math']
        elif subject == "english":
            timeout = config.TIME_LIMITS['english']
        elif subject == "analytical":
            # Check if it's a puzzle
            if 'topic' in question_data and question_data.get('topic') == "puzzle":
                timeout = config.TIME_LIMITS['puzzle']
            else:
                timeout = config.TIME_LIMITS['analytical']
        else:
            timeout = 60  # Default fallback
            
        super().__init__(timeout=timeout)
        self.question_data = question_data
        self.subject = subject
        self.user_id = user_id
        
        for i, option in enumerate(question_data['options']):
            self.add_item(QuestionButton(option, i, question_data['correct_answer']))

class QuestionButton(discord.ui.Button):
    def __init__(self, option, index, correct_index):
        super().__init__(label=option, style=discord.ButtonStyle.secondary)
        self.index = index
        self.correct_index = correct_index
    
    async def callback(self, interaction: discord.Interaction):
        user_id = interaction.user.id
        
        if user_id not in active_questions:
            await interaction.response.send_message("Question expired", ephemeral=True)
            return
        
        # 🔥 FIX: Get fresh user data from database
        user_data = db._read_data().get(str(user_id), {})
        if not user_data:
            user_data = db.create_user(user_id)
        
        question_data = active_questions[user_id]
        subject = question_data['subject']
        topic = question_data['topic']
        
        # Increment question count - ensure this works
        db.increment_questions_answered(user_id)
        
        # Update local user_data with fresh values
        user_data = db.get_user(user_id)  # Get updated data
        
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
            result_text = f"Incorrect! ❌ Correct answer: {question_data['question']['options'][self.correct_index]}"
            color = discord.Color.red()
        
        user_data[subject] = subject_data
        db.update_user(user_id, user_data)
        lb.update_score(user_id, user_data['total_score'])
        
        embed = discord.Embed(title=result_text, color=color)
        embed.add_field(name="Your Answer", value=self.label, inline=True)
        embed.add_field(name="Score", value=user_data['total_score'], inline=True)
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
        
        if user_id in active_questions:
            active_questions[user_id]['timeout'].cancel()
            try:
                await active_questions[user_id]['message'].edit(view=None)
            except:
                pass
            del active_questions[user_id]

# Timeout handler
async def question_timeout(user_id, timeout):
    await asyncio.sleep(timeout)
    if user_id in active_questions:
        user_data = db.get_user(user_id) or db.create_user(user_id)
        question_data = active_questions[user_id]
        subject = question_data['subject']
        
        subject_data = user_data.get(subject, {})
        subject_data['total'] = subject_data.get('total', 0) + 1
        subject_data['timeout'] = subject_data.get('timeout', 0) + 1
        user_data[subject] = subject_data
        db.update_user(user_id, user_data)
        
        try:
            await active_questions[user_id]['message'].edit(content="Time's up!", view=None)
        except:
            pass
        del active_questions[user_id]

@bot.tree.command(name="mystatus", description="Check your access status and remaining questions")
async def my_status(interaction: discord.Interaction):
    user_id = interaction.user.id
    
    # 🔥 CRITICAL FIX: Force refresh user data from database
    # This ensures we get the most current data
    user_data = db._read_data().get(str(user_id), {})
    
    # If user doesn't exist in database, create them
    if not user_data:
        user_data = db.create_user(user_id)
    else:
        # Refresh premium status
        if user_data.get('premium_until'):
            try:
                premium_until = datetime.fromisoformat(user_data['premium_until'])
                if datetime.now() > premium_until:
                    user_data['premium_access'] = False
                    user_data['premium_until'] = None
                    db.update_user(user_id, user_data)
            except:
                user_data['premium_access'] = False
                user_data['premium_until'] = None
                db.update_user(user_id, user_data)
    
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
    
    # Question usage - FIXED: Use the refreshed data
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

# ADMIN COMMANDS
@admin_group.command(name="add_ticket", description="Add premium access to a user")
@app_commands.choices(duration=[
    app_commands.Choice(name="7 Days", value="7days"),
    app_commands.Choice(name="14 Days", value="14days"),
    app_commands.Choice(name="1 Month", value="1month"),
    app_commands.Choice(name="3 Months", value="3months")
])
async def add_ticket(interaction: discord.Interaction, user: discord.User, duration: app_commands.Choice[str]):
    try:
        print(f"🎫 Admin command received from {interaction.user.id} for user {user.id}")
        
        # Check if user is admin
        user_data = db.get_user(interaction.user.id)
        is_admin = user_data.get('is_admin') or interaction.user.id in config.PREMIUM_SETTINGS["admin_ids"]
        
        print(f"🔍 Admin check: User {interaction.user.id}, is_admin: {is_admin}")
        print(f"🔍 Admin IDs in config: {config.PREMIUM_SETTINGS['admin_ids']}")
        
        if not is_admin:
            await interaction.response.send_message("❌ Admin access required.", ephemeral=True)
            return
        
        # Add premium access
        days = config.PREMIUM_SETTINGS["ticket_durations"][duration.value]
        print(f"📅 Adding {days} days premium for user {user.id}")
        
        premium_until = db.add_premium_access(user.id, days)
        
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
        except Exception as e:
            print(f"❌ Could not DM user: {e}")
            
    except Exception as e:
        print(f"❌ Error in add_ticket command: {e}")
        import traceback
        traceback.print_exc()
        await interaction.response.send_message(f"❌ Error: {str(e)}", ephemeral=True)

@admin_group.command(name="check_access", description="Check a user's access status")
async def check_access(interaction: discord.Interaction, user: discord.User):
    try:
        user_data = db.get_user(user.id)
        access_control = AccessControl(db)
        
        embed = discord.Embed(title=f"Access Status: {user.display_name}", color=discord.Color.blue())
        
        # Premium status
        if user_data.get('premium_access'):
            premium_until = datetime.fromisoformat(user_data['premium_until'])
            embed.add_field(name="Premium Status", value=f"✅ Active until {premium_until.strftime('%Y-%m-%d')}", inline=False)
        else:
            embed.add_field(name="Premium Status", value="❌ No active subscription", inline=False)
        
        # Question usage
        questions_answered = user_data.get('questions_answered', 0)
        remaining = access_control.get_remaining_questions(user.id)
        embed.add_field(name="Question Usage", value=f"**Answered:** {questions_answered}\n**Remaining free:** {remaining}", inline=False)
        
        # Admin status
        if user_data.get('is_admin') or user.id in config.PREMIUM_SETTINGS["admin_ids"]:
            embed.add_field(name="Admin", value="✅ Yes", inline=True)
        else:
            embed.add_field(name="Admin", value="❌ No", inline=True)
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
        
    except Exception as e:
        print(f"❌ Error in check_access command: {e}")
        await interaction.response.send_message(f"❌ Error: {str(e)}", ephemeral=True)

@bot.tree.command(name="admin_test", description="Test if you have admin access")
async def admin_test(interaction: discord.Interaction):
    try:
        user_data = db.get_user(interaction.user.id)
        is_admin = user_data.get('is_admin') or interaction.user.id in config.PREMIUM_SETTINGS["admin_ids"]
        
        if is_admin:
            await interaction.response.send_message("✅ You have admin access!", ephemeral=True)
        else:
            await interaction.response.send_message("❌ You do NOT have admin access!", ephemeral=True)
            
    except Exception as e:
        print(f"❌ Error in admin_test command: {e}")
        await interaction.response.send_message(f"❌ Error: {str(e)}", ephemeral=True)

@bot.tree.command(name="debug_commands", description="List all available commands")
async def debug_commands(interaction: discord.Interaction):
    if interaction.user.id not in config.PREMIUM_SETTINGS["admin_ids"]:
        await interaction.response.send_message("❌ Admin only command.", ephemeral=True)
        return
    
    try:
        commands = await bot.tree.fetch_commands()
        command_list = "\n".join([f"/{cmd.name}" for cmd in commands])
        await interaction.response.send_message(f"Available commands:\n{command_list}", ephemeral=True)
    except Exception as e:
        print(f"❌ Error in debug_commands: {e}")
        await interaction.response.send_message(f"❌ Error: {str(e)}", ephemeral=True)

# Register the admin group with the bot
bot.tree.add_command(admin_group)

# Run the bot
if __name__ == "__main__":
    bot.run(config.BOT_TOKEN)

