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

@bot.event
async def on_interaction(interaction: discord.Interaction):
    try:
        # Process the interaction
        await bot.process_application_commands(interaction)
    except Exception as e:
        print(f"Interaction error: {e}")
        try:
            if not interaction.response.is_done():
                await interaction.response.send_message("An error occurred with this interaction.", ephemeral=True)
        except:
            pass

async def question_timeout(user_id, timeout):
    """Handle question timeout"""
    try:
        await asyncio.sleep(timeout)
        if user_id in active_questions and not active_questions[user_id].get('view', {}).answered:
            question_data = active_questions[user_id]
            view = question_data.get('view')
            
            if view:
                view.answered = True
                
                # Disable all buttons
                for item in view.children:
                    if isinstance(item, discord.ui.Button):
                        item.disabled = True
                
                # Update the message if it exists
                if hasattr(view, 'message') and view.message:
                    try:
                        await view.message.edit(view=view)
                    except (discord.NotFound, discord.HTTPException):
                        pass
                
                # Update database for timeout
                try:
                    user_data = await db.get_user(user_id)
                    subject = question_data['subject']
                    
                    # Initialize subject data if not exists
                    if subject not in user_data:
                        user_data[subject] = {'correct': 0, 'total': 0, 'timeout': 0, 'topics': {}}
                    
                    subject_data = user_data[subject]
                    subject_data['total'] = subject_data.get('total', 0) + 1
                    subject_data['timeout'] = subject_data.get('timeout', 0) + 1
                    
                    user_data[subject] = subject_data
                    await db.update_user(user_id, user_data)
                    print(f"Timeout recorded for user {user_id}")
                except Exception as e:
                    print(f"Error updating database on timeout: {e}")
                
    except asyncio.CancelledError:
        # Task was cancelled, which is normal when user answers
        print(f"Timeout task cancelled for user {user_id}")
        pass
    except Exception as e:
        print(f"Error in question_timeout: {e}")
    finally:
        # Clean up
        if user_id in active_questions:
            del active_questions[user_id]
            print(f"Cleaned up active question for user {user_id}")

@bot.event
async def on_app_command_completion(interaction: discord.Interaction, command: app_commands.Command):
    print(f"Command {command.name} completed by {interaction.user}")

@bot.tree.command(name="math_practice", description="Practice math questions")
@app_commands.choices(topic=[app_commands.Choice(name=name, value=name) for name in config.MATH_TOPICS])
print(f"Starting {subject} practice for user {user_id}, topic: {topic.value}")
async def math_practice(interaction: discord.Interaction, topic: app_commands.Choice[str]):
    """Handle math practice command with proper error handling"""
    try:
        user_id = interaction.user.id
        
        # Defer the response first to prevent interaction timeout
        if not interaction.response.is_done():
            await interaction.response.defer(thinking=True, ephemeral=True)
        else:
            # If already responded, we need to handle differently
            try:
                await interaction.followup.send("Processing your request...", ephemeral=True)
            except:
                pass
        
        # Check if user already has an active question
        if user_id in active_questions:
            try:
                await interaction.followup.send("You already have an active question. Please answer it first.", ephemeral=True)
            except discord.errors.NotFound:
                try:
                    await interaction.edit_original_response(content="You already have an active question. Please answer it first.")
                except:
                    pass
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
                await interaction.followup.send(f"No questions found for {topic.value}", ephemeral=True)
            except:
                try:
                    await interaction.edit_original_response(content=f"No questions found for {topic.value}")
                except:
                    pass
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
        
        view = QuestionView(question_data, "math", user_id, config.TIME_LIMITS['math'])
        
        # Send the question
        try:
            if file:
                await interaction.followup.send(embed=embed, file=file, view=view, ephemeral=True)
            else:
                await interaction.followup.send(embed=embed, view=view, ephemeral=True)
            
            # Get the message reference
            message = await interaction.original_response()
            view.message = message
            
            # Store active question
            active_questions[user_id] = {
                "question": question_data,
                "subject": "math",
                "topic": topic.value,
                "view": view,
                "message": message,
                "timeout": asyncio.create_task(question_timeout(user_id, config.TIME_LIMITS['math']))
            }
            
        except Exception as e:
            print(f"Error sending math question: {e}")
            try:
                await interaction.followup.send("Failed to send the question. Please try again.", ephemeral=True)
            except:
                pass
            
    except Exception as e:
        print(f"Error in math_practice: {e}")
        try:
            if not interaction.response.is_done():
                await interaction.response.send_message("An error occurred. Please try again.", ephemeral=True)
            else:
                await interaction.followup.send("An error occurred. Please try again.", ephemeral=True)
        except:
            pass

@bot.tree.command(name="english_practice", description="Practice English questions")
@app_commands.choices(topic=[app_commands.Choice(name=name, value=name) for name in config.ENGLISH_TOPICS])
print(f"Starting {subject} practice for user {user_id}, topic: {topic.value}")
async def english_practice(interaction: discord.Interaction, topic: app_commands.Choice[str]):
    """Handle English practice command with proper error handling"""
    try:
        user_id = interaction.user.id
        
        # Defer the response first to prevent interaction timeout
        if not interaction.response.is_done():
            await interaction.response.defer(thinking=True, ephemeral=True)
        else:
            try:
                await interaction.followup.send("Processing your request...", ephemeral=True)
            except:
                pass
        
        # Check if user already has an active question
        if user_id in active_questions:
            try:
                await interaction.followup.send("You already have an active question. Please answer it first.", ephemeral=True)
            except:
                try:
                    await interaction.edit_original_response(content="You already have an active question. Please answer it first.")
                except:
                    pass
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
                await interaction.followup.send(f"No questions found for {topic.value}", ephemeral=True)
            except:
                try:
                    await interaction.edit_original_response(content=f"No questions found for {topic.value}")
                except:
                    pass
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
        
        view = QuestionView(question_data, "english", user_id, config.TIME_LIMITS['english'])
        
        # Send the question
        try:
            if file:
                await interaction.followup.send(embed=embed, file=file, view=view, ephemeral=True)
            else:
                await interaction.followup.send(embed=embed, view=view, ephemeral=True)
            
            # Get the message reference
            message = await interaction.original_response()
            view.message = message

            timeout_task = asyncio.create_task(question_timeout(user_id, time_limit))
            active_questions[user_id] = {
                "question": question_data,
                "subject": subject,
                "topic": topic.value,
                "view": view,
                "message": message,
                "timeout": timeout_task
            }
                
        except Exception as e:
            print(f"Error sending English question: {e}")
            try:
                await interaction.followup.send("Failed to send the question. Please try again.", ephemeral=True)
            except:
                pass
            
    except Exception as e:
        print(f"Error in english_practice: {e}")
        try:
            if not interaction.response.is_done():
                await interaction.response.send_message("An error occurred. Please try again.", ephemeral=True)
            else:
                await interaction.followup.send("An error occurred. Please try again.", ephemeral=True)
        except:
            pass

@bot.tree.command(name="analytical_practice", description="Practice analytical questions")
@app_commands.choices(topic=[app_commands.Choice(name=name, value=name) for name in config.ANALYTICAL_TOPICS])
print(f"Starting {subject} practice for user {user_id}, topic: {topic.value}")
async def analytical_practice(interaction: discord.Interaction, topic: app_commands.Choice[str]):
    """Handle analytical practice command with proper error handling"""
    try:
        user_id = interaction.user.id
        
        # Defer the response first to prevent interaction timeout
        if not interaction.response.is_done():
            await interaction.response.defer(thinking=True, ephemeral=True)
        else:
            try:
                await interaction.followup.send("Processing your request...", ephemeral=True)
            except:
                pass
        
        # Check if user already has an active question
        if user_id in active_questions:
            try:
                await interaction.followup.send("You already have an active question. Please answer it first.", ephemeral=True)
            except:
                try:
                    await interaction.edit_original_response(content="You already have an active question. Please answer it first.")
                except:
                    pass
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
                await interaction.followup.send(f"No questions found for {topic.value}", ephemeral=True)
            except:
                try:
                    await interaction.edit_original_response(content=f"No questions found for {topic.value}")
                except:
                    pass
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
        
        view = QuestionView(question_data, "analytical", user_id, time_limit)
        
        # Send the question
        try:
            if file:
                await interaction.followup.send(embed=embed, file=file, view=view, ephemeral=True)
            else:
                await interaction.followup.send(embed=embed, view=view, ephemeral=True)
            
            # Get the message reference
            message = await interaction.original_response()
            view.message = message
            
            # Store active question
            active_questions[user_id] = {
                "question": question_data,
                "subject": "analytical",
                "topic": topic.value,
                "view": view,
                "message": message,
                "timeout": asyncio.create_task(question_timeout(user_id, time_limit))
            }
            
        except Exception as e:
            print(f"Error sending analytical question: {e}")
            try:
                await interaction.followup.send("Failed to send the question. Please try again.", ephemeral=True)
            except:
                pass
            
    except Exception as e:
        print(f"Error in analytical_practice: {e}")
        try:
            if not interaction.response.is_done():
                await interaction.response.send_message("An error occurred. Please try again.", ephemeral=True)
            else:
                await interaction.followup.send("An error occurred. Please try again.", ephemeral=True)
        except:
            pass

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

class QuestionView(discord.ui.View):
    def __init__(self, question_data, subject, user_id, timeout_duration):
        super().__init__(timeout=None)  # We handle timeout manually
        self.question_data = question_data
        self.subject = subject
        self.user_id = user_id
        self.message = None
        self.answered = False
        
        for i, option in enumerate(question_data['options']):
            self.add_item(QuestionButton(option, i, question_data['correct_answer']))
                    
class QuestionButton(discord.ui.Button):
    def __init__(self, option, index, correct_index):
        super().__init__(label=option, style=discord.ButtonStyle.secondary)
        self.index = index
        self.correct_index = correct_index
    
    async def callback(self, interaction: discord.Interaction):
        user_id = interaction.user.id
        print(f"Button clicked by user {user_id}")
        
        # Check if interaction is already responded to
        if interaction.response.is_done():
            print("Interaction already responded to")
            return
            
        try:
            # Check if user has an active question
            if user_id not in active_questions:
                print(f"No active question for user {user_id}")
                await interaction.response.send_message("Question expired or already answered", ephemeral=True)
                return
            
            # Get the question data
            question_data = active_questions[user_id]
            view = question_data.get('view')
            
            if not view:
                print("No view found in question data")
                await interaction.response.send_message("Question data is invalid", ephemeral=True)
                if user_id in active_questions:
                    del active_questions[user_id]
                return
            
            # Check if already answered
            if getattr(view, 'answered', False):
                print("Question already answered")
                await interaction.response.send_message("You already answered this question!", ephemeral=True)
                return
            
            # Mark as answered immediately
            view.answered = True
            
            # Cancel timeout task if it exists
            if 'timeout' in active_questions[user_id]:
                try:
                    active_questions[user_id]['timeout'].cancel()
                    print("Timeout task cancelled")
                except Exception as e:
                    print(f"Error cancelling timeout: {e}")
            
            # Disable all buttons
            for item in view.children:
                if isinstance(item, discord.ui.Button):
                    item.disabled = True
            
            # Update the message to show disabled buttons (non-blocking)
            asyncio.create_task(self._disable_buttons(interaction.message, view))
            
            # Process the answer
            await self._process_answer(interaction, user_id, question_data)
            
        except Exception as e:
            print(f"Unexpected error in button callback: {e}")
            try:
                if not interaction.response.is_done():
                    await interaction.response.send_message("An error occurred. Please try again.", ephemeral=True)
            except:
                pass
            finally:
                # Clean up on error
                if user_id in active_questions:
                    del active_questions[user_id]
    
    async def _disable_buttons(self, message, view):
        """Disable buttons without blocking the main callback"""
        try:
            await message.edit(view=view)
        except (discord.NotFound, discord.HTTPException) as e:
            print(f"Could not disable buttons: {e}")
    
    async def _process_answer(self, interaction, user_id, question_data):
        """Process the answer separately"""
        try:
            # Get user data
            user_data = await db.get_user(user_id)
            subject = question_data['subject']
            
            # Update question count
            await db.increment_questions_answered(user_id)
            
            # Initialize subject data if not exists
            if subject not in user_data:
                user_data[subject] = {'correct': 0, 'total': 0, 'topics': {}}
            
            subject_data = user_data[subject]
            subject_data['total'] = subject_data.get('total', 0) + 1
            
            # Check if answer is correct
            is_correct = self.index == self.correct_index
            
            # Update scores
            if is_correct:
                user_data['total_score'] = user_data.get('total_score', 0) + config.SCORING['correct']
                subject_data['correct'] = subject_data.get('correct', 0) + 1
                result_text = "Correct! ✅"
                color = discord.Color.green()
            else:
                user_data['total_score'] = user_data.get('total_score', 0) + config.SCORING['incorrect']
                result_text = f"Incorrect! ❌ Correct answer: {question_data['question']['options'][self.correct_index]}"
                color = discord.Color.red()
            
            # Update user data
            user_data[subject] = subject_data
            await db.update_user(user_id, user_data)
            await db.update_leaderboard(user_id, user_data['total_score'])
            
            # Send result
            embed = discord.Embed(title=result_text, color=color)
            embed.add_field(name="Your Answer", value=self.label, inline=True)
            embed.add_field(name="Score", value=user_data['total_score'], inline=True)
            
            # Send response
            if interaction.response.is_done():
                await interaction.followup.send(embed=embed, ephemeral=True)
            else:
                await interaction.response.send_message(embed=embed, ephemeral=True)
                
            print(f"Answer processed successfully for user {user_id}")
            
        except Exception as e:
            print(f"Error processing answer: {e}")
            if not interaction.response.is_done():
                await interaction.response.send_message("Error processing your answer.", ephemeral=True)
            else:
                await interaction.followup.send("Error processing your answer.", ephemeral=True)
        finally:
            # Always clean up
            if user_id in active_questions:
                del active_questions[user_id]

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





