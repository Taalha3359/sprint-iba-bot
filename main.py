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

# Setup bot
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix=config.BOT_PREFIX, intents=intents)

# Initialize components
db = UserDatabase()
qm = QuestionManager()
lb = Leaderboard()

# Store active questions
active_questions = {}

@bot.event
async def on_ready():
    print(f'{bot.user} is now online!')
    try:
        synced = await bot.tree.sync()
        print(f"Loaded {len(synced)} commands")
    except Exception as e:
        print(f"Error: {e}")

# Math practice command
@bot.tree.command(name="math_practice", description="Practice math questions")
@app_commands.choices(topic=[
    app_commands.Choice(name=name, value=name) for name in config.MATH_TOPICS
])
async def math_practice(interaction: discord.Interaction, topic: app_commands.Choice[str]):
    user_id = interaction.user.id
    
    if user_id in active_questions:
        await interaction.response.send_message("Finish your current question first!", ephemeral=True)
        return
    
    question_data = qm.get_question("math", topic.value)
    if not question_data:
        await interaction.response.send_message(f"No questions found for {topic.value}", ephemeral=True)
        return
    
    embed = discord.Embed(
        title=f"Math - {topic.value}",
        description=f"**Question:**\n{question_data['question']}",
        color=discord.Color.blue()
    )
    embed.set_footer(text=f"You have {config.TIME_LIMITS['math']} seconds")
    
    # Add image if available
    if question_data.get('image_path'):
        file = discord.File(question_data['image_path'], filename="question.png")
        embed.set_image(url="attachment://question.png")
    else:
        file = None
    
    view = QuestionView(question_data, "math", user_id)
    
    if file:
        await interaction.response.send_message(embed=embed, file=file, view=view, ephemeral=True)
    else:
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
    
    active_questions[user_id] = {
        "question": question_data,
        "subject": "math",
        "topic": topic.value,
        "message": await interaction.original_response(),
        "timeout": asyncio.create_task(question_timeout(user_id, config.TIME_LIMITS['math']))
    }

# English practice command
@bot.tree.command(name="english_practice", description="Practice English questions")
@app_commands.choices(topic=[
    app_commands.Choice(name=name, value=name) for name in config.ENGLISH_TOPICS
])
async def english_practice(interaction: discord.Interaction, topic: app_commands.Choice[str]):
    user_id = interaction.user.id
    
    if user_id in active_questions:
        await interaction.response.send_message("Finish your current question first!", ephemeral=True)
        return
    
    question_data = qm.get_question("english", topic.value)
    if not question_data:
        await interaction.response.send_message(f"No questions found for {topic.value}", ephemeral=True)
        return
    
    embed = discord.Embed(
        title=f"English - {topic.value}",
        description=f"**Question:**\n{question_data['question']}",
        color=discord.Color.green()
    )
    embed.set_footer(text=f"You have {config.TIME_LIMITS['english']} seconds")
    
    if question_data.get('image_path'):
        file = discord.File(question_data['image_path'], filename="question.png")
        embed.set_image(url="attachment://question.png")
    else:
        file = None
    
    view = QuestionView(question_data, "english", user_id)
    
    if file:
        await interaction.response.send_message(embed=embed, file=file, view=view, ephemeral=True)
    else:
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
    
    active_questions[user_id] = {
        "question": question_data,
        "subject": "english",
        "topic": topic.value,
        "message": await interaction.original_response(),
        "timeout": asyncio.create_task(question_timeout(user_id, config.TIME_LIMITS['english']))
    }

# Analytical practice command
@bot.tree.command(name="analytical_practice", description="Practice analytical questions")
@app_commands.choices(topic=[
    app_commands.Choice(name=name, value=name) for name in config.ANALYTICAL_TOPICS
])
async def analytical_practice(interaction: discord.Interaction, topic: app_commands.Choice[str]):
    user_id = interaction.user.id
    
    if user_id in active_questions:
        await interaction.response.send_message("Finish your current question first!", ephemeral=True)
        return
    
    question_data = qm.get_question("analytical", topic.value)
    if not question_data:
        await interaction.response.send_message(f"No questions found for {topic.value}", ephemeral=True)
        return
    
    # Use puzzle time for puzzles, regular for others
    time_limit = config.TIME_LIMITS['puzzle'] if topic.value == "puzzle" else config.TIME_LIMITS['analytical']
    
    embed = discord.Embed(
        title=f"Analytical - {topic.value}",
        description=f"**Question:**\n{question_data['question']}",
        color=discord.Color.orange()
    )
    embed.set_footer(text=f"You have {time_limit} seconds")
    
    if question_data.get('image_path'):
        file = discord.File(question_data['image_path'], filename="question.png")
        embed.set_image(url="attachment://question.png")
    else:
        file = None
    
    view = QuestionView(question_data, "analytical", user_id)
    
    if file:
        await interaction.response.send_message(embed=embed, file=file, view=view, ephemeral=True)
    else:
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
    
    active_questions[user_id] = {
        "question": question_data,
        "subject": "analytical",
        "topic": topic.value,
        "message": await interaction.original_response(),
        "timeout": asyncio.create_task(question_timeout(user_id, time_limit))
    }

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

# Question view with buttons
class QuestionView(discord.ui.View):
    def __init__(self, question_data, subject, user_id):
        super().__init__(timeout=None)
        self.question_data = question_data
        self.subject = subject
        self.user_id = user_id
        
        for i, option in enumerate(question_data['options']):
            self.add_item(QuestionButton(option, i, question_data['correct_answer']))
    
    async def on_timeout(self):
        if self.user_id in active_questions:
            user_data = db.get_user(self.user_id) or db.create_user(self.user_id)
            subject_data = user_data.get(self.subject, {})
            subject_data['total'] = subject_data.get('total', 0) + 1
            subject_data['timeout'] = subject_data.get('timeout', 0) + 1
            user_data[self.subject] = subject_data
            db.update_user(self.user_id, user_data)
            
            if self.user_id in active_questions:
                try:
                    await active_questions[self.user_id]['message'].edit(content="Time's up!", view=None)
                except:
                    pass
                del active_questions[self.user_id]

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
        
        user_data = db.get_user(user_id) or db.create_user(user_id)
        question_data = active_questions[user_id]
        subject = question_data['subject']
        topic = question_data['topic']
        
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

# Run the bot
if __name__ == "__main__":
    bot.run(config.BOT_TOKEN)