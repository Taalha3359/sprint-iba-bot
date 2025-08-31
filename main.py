import discord
from discord.ext import commands, tasks
from discord import app_commands
import asyncio
import os
import random
import json
from datetime import datetime, timedelta

import config
from database import MongoDB
from question_manager import QuestionManager
from access_control import AccessControl

# Setup bot
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix=config.BOT_PREFIX, intents=intents)

# Initialize components
db = MongoDB()
qm = QuestionManager()
access_control = AccessControl(db)

# Store active questions and timeout tasks
active_questions = {}
timeout_tasks = {}

class QuestionView(discord.ui.View):
    def __init__(self, question_data, subject, topic, time_limit):
        super().__init__(timeout=time_limit)
        self.question_data = question_data
        self.subject = subject
        self.topic = topic
        self.answered = False
        self.correct_index = question_data['correct_answer']
        
        # Add buttons for each option
        for i, option in enumerate(question_data['options']):
            self.add_item(QuestionButton(option, i, self.correct_index))

class QuestionButton(discord.ui.Button):
    def __init__(self, label, index, correct_index):
        super().__init__(label=label, style=discord.ButtonStyle.primary)
        self.index = index
        self.correct_index = correct_index
    
    async def callback(self, interaction: discord.Interaction):
        # Defer the response first
        await interaction.response.defer()
        
        user_id = interaction.user.id
        
        # Check if this question is still active
        if user_id not in active_questions:
            await interaction.followup.send("This question has expired or was already answered.", ephemeral=True)
            return
        
        question_info = active_questions[user_id]
        view = question_info['view']
        
        # Check if already answered
        if view.answered:
            await interaction.followup.send("You already answered this question!", ephemeral=True)
            return
        
        # Mark as answered
        view.answered = True
        view.stop()
        
        # Cancel timeout task if it exists
        if user_id in timeout_tasks:
            timeout_tasks[user_id].cancel()
            del timeout_tasks[user_id]
        
        # Disable all buttons
        for item in view.children:
            item.disabled = True
        
        # Update the message to show disabled buttons
        try:
            await interaction.message.edit(view=view)
        except:
            pass
        
        # Process the answer
        is_correct = self.index == self.correct_index
        
        # Get user data
        user_data = await db.get_user(user_id)
        
        # Update scores
        if is_correct:
            score_change = config.SCORING['correct']
            result_text = "Correct! ✅"
            color = discord.Color.green()
        else:
            score_change = config.SCORING['incorrect']
            correct_answer = question_info['question_data']['options'][self.correct_index]
            result_text = f"Incorrect! ❌ Correct answer: {correct_answer}"
            color = discord.Color.red()
        
        # Update user data
        user_data['total_score'] = user_data.get('total_score', 0) + score_change
        user_data['questions_answered'] = user_data.get('questions_answered', 0) + 1
        
        # Update subject-specific stats
        subject = question_info['subject']
        if subject not in user_data:
            user_data[subject] = {'correct': 0, 'total': 0}
        
        user_data[subject]['total'] = user_data[subject].get('total', 0) + 1
        if is_correct:
            user_data[subject]['correct'] = user_data[subject].get('correct', 0) + 1
        
        await db.update_user(user_id, user_data)
        
        # Send result
        embed = discord.Embed(
            title=result_text,
            description=f"**Your score:** {user_data['total_score']}",
            color=color
        )
        
        await interaction.followup.send(embed=embed, ephemeral=True)
        
        # Clean up
        if user_id in active_questions:
            del active_questions[user_id]

@bot.event
async def on_ready():
    print(f'{bot.user} is now online!')
    
    try:
        synced = await bot.tree.sync()
        print(f"Loaded {len(synced)} commands")
    except Exception as e:
        print(f"Error syncing commands: {e}")

async def send_question(interaction, subject, topic):
    user_id = interaction.user.id
    
    # Check if user already has an active question
    if user_id in active_questions:
        await interaction.followup.send("You already have an active question. Please answer it first.", ephemeral=True)
        return
    
    # Check access
    has_access, access_type = await access_control.check_access(interaction)
    if not has_access:
        await access_control.send_access_denied_message(interaction, access_type)
        return
    
    # Get question
    question_data = qm.get_question(subject, topic)
    if not question_data:
        await interaction.followup.send(f"No questions found for {topic}", ephemeral=True)
        return
    
    # Determine time limit
    time_limit = config.TIME_LIMITS.get(subject, 60)
    
    # Create embed
    embed = discord.Embed(
        title=f"{subject.capitalize()} - {topic}",
        description=f"**Question:**\n{question_data['question']}",
        color=discord.Color.blue()
    )
    embed.set_footer(text=f"You have {time_limit} seconds to answer")
    
    # Create view with buttons
    view = QuestionView(question_data, subject, topic, time_limit)
    
    # Send question
    message = await interaction.followup.send(embed=embed, view=view, ephemeral=True)
    
    # Store active question
    active_questions[user_id] = {
        'question_data': question_data,
        'subject': subject,
        'topic': topic,
        'view': view,
        'message': message
    }
    
    # Set up timeout task
    timeout_tasks[user_id] = asyncio.create_task(handle_timeout(user_id, time_limit))

async def handle_timeout(user_id, timeout):
    try:
        await asyncio.sleep(timeout)
        
        if user_id in active_questions:
            question_info = active_questions[user_id]
            view = question_info['view']
            
            if not view.answered:
                # Mark as answered and disable buttons
                view.answered = True
                for item in view.children:
                    item.disabled = True
                
                try:
                    await question_info['message'].edit(view=view)
                except:
                    pass
                
                # Update database for timeout
                user_data = await db.get_user(user_id)
                subject = question_info['subject']
                
                if subject not in user_data:
                    user_data[subject] = {'correct': 0, 'total': 0}
                
                user_data[subject]['total'] = user_data[subject].get('total', 0) + 1
                user_data['questions_answered'] = user_data.get('questions_answered', 0) + 1
                
                await db.update_user(user_id, user_data)
                
                # Send timeout message
                try:
                    await question_info['message'].reply("⏰ Time's up! Question expired.", ephemeral=True)
                except:
                    pass
                
                # Clean up
                del active_questions[user_id]
                if user_id in timeout_tasks:
                    del timeout_tasks[user_id]
                    
    except asyncio.CancelledError:
        # Task was cancelled (user answered)
        pass
    except Exception as e:
        print(f"Error in timeout handler: {e}")
        if user_id in active_questions:
            del active_questions[user_id]
        if user_id in timeout_tasks:
            del timeout_tasks[user_id]

# Math command
@bot.tree.command(name="math_practice", description="Practice math questions")
@app_commands.choices(topic=[app_commands.Choice(name=name, value=name) for name in config.MATH_TOPICS])
async def math_practice(interaction: discord.Interaction, topic: app_commands.Choice[str]):
    await interaction.response.defer(ephemeral=True)
    await send_question(interaction, "math", topic.value)

# English command
@bot.tree.command(name="english_practice", description="Practice English questions")
@app_commands.choices(topic=[app_commands.Choice(name=name, value=name) for name in config.ENGLISH_TOPICS])
async def english_practice(interaction: discord.Interaction, topic: app_commands.Choice[str]):
    await interaction.response.defer(ephemeral=True)
    await send_question(interaction, "english", topic.value)

# Analytical command
@bot.tree.command(name="analytical_practice", description="Practice analytical questions")
@app_commands.choices(topic=[app_commands.Choice(name=name, value=name) for name in config.ANALYTICAL_TOPICS])
async def analytical_practice(interaction: discord.Interaction, topic: app_commands.Choice[str]):
    await interaction.response.defer(ephemeral=True)
    await send_question(interaction, "analytical", topic.value)

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

# Error handling
@bot.event
async def on_app_command_error(interaction, error):
    print(f"Error: {error}")
    try:
        await interaction.response.send_message("An error occurred. Please try again.", ephemeral=True)
    except:
        pass

# Run the bot
if __name__ == "__main__":
    bot.run(config.BOT_TOKEN)
