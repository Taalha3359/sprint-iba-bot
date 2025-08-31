import discord
from discord.ext import commands
from discord import app_commands
import asyncio
import os
import random

import config
from utils.database import MongoDB
from utils.question_manager import QuestionManager
from utils.access_control import AccessControl

# Setup bot
intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix=config.BOT_PREFIX, intents=intents)

# Initialize components
db = MongoDB()
qm = QuestionManager()
access_control = AccessControl(db)

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

class QuestionView(discord.ui.View):
    def __init__(self, question_data, subject, user_id):
        super().__init__(timeout=config.TIME_LIMITS.get(subject, 60))
        self.question_data = question_data
        self.subject = subject
        self.user_id = user_id
        
        for i, option in enumerate(question_data['options']):
            self.add_item(QuestionButton(option, i, question_data['correct_answer']))

class QuestionButton(discord.ui.Button):
    def __init__(self, option, index, correct_index):
        super().__init__(label=option, style=discord.ButtonStyle.primary)
        self.index = index
        self.correct_index = correct_index
    
    async def callback(self, interaction: discord.Interaction):
        user_id = interaction.user.id
        
        # Only allow the original user to answer
        if user_id != self.view.user_id:
            await interaction.response.send_message("This is not your question!", ephemeral=True)
            return
        
        # Disable all buttons
        for item in self.view.children:
            item.disabled = True
        
        await interaction.message.edit(view=self.view)
        
        # Process answer
        is_correct = self.index == self.correct_index
        
        if is_correct:
            result_text = "Correct! ✅"
            color = discord.Color.green()
            score_change = config.SCORING['correct']
        else:
            correct_answer = self.view.question_data['options'][self.correct_index]
            result_text = f"Incorrect! ❌ Correct answer: {correct_answer}"
            color = discord.Color.red()
            score_change = config.SCORING['incorrect']
        
        # Update user data
        user_data = await db.get_user(user_id)
        user_data['total_score'] = user_data.get('total_score', 0) + score_change
        user_data['questions_answered'] = user_data.get('questions_answered', 0) + 1
        
        # Update subject stats
        subject = self.view.subject
        if subject not in user_data:
            user_data[subject] = {'correct': 0, 'total': 0}
        
        user_data[subject]['total'] = user_data[subject].get('total', 0) + 1
        if is_correct:
            user_data[subject]['correct'] = user_data[subject].get('correct', 0) + 1
        
        await db.update_user(user_id, user_data)
        await db.update_leaderboard(user_id, user_data['total_score'])
        
        # Send result
        embed = discord.Embed(title=result_text, color=color)
        embed.add_field(name="Your Answer", value=self.label, inline=True)
        embed.add_field(name="Score", value=user_data['total_score'], inline=True)
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
        
        # Remove from active questions
        if user_id in active_questions:
            del active_questions[user_id]

async def send_question(interaction, subject, topic):
    """Send a question to the user"""
    user_id = interaction.user.id
    
    # Check if user already has an active question
    if user_id in active_questions:
        await interaction.response.send_message("You already have an active question. Please answer it first.", ephemeral=True)
        return
    
    # Check access
    has_access, access_type = await access_control.check_access(interaction)
    if not has_access:
        await access_control.send_access_denied_message(interaction, access_type)
        return
    
    # Get question
    question_data = qm.get_question(subject, topic)
    if not question_data:
        await interaction.response.send_message(f"No questions found for {topic}", ephemeral=True)
        return
    
    # Create embed
    time_limit = config.TIME_LIMITS.get(subject, 60)
    embed = discord.Embed(
        title=f"{subject.capitalize()} - {topic}",
        description=f"**Question:**\n{question_data['question']}",
        color=discord.Color.blue()
    )
    embed.set_footer(text=f"You have {time_limit} seconds")
    
    # Handle image
    file = None
    if question_data.get('image_path') and os.path.exists(question_data['image_path']):
        file = discord.File(question_data['image_path'], filename="question.png")
        embed.set_image(url="attachment://question.png")
    
    view = QuestionView(question_data, subject, user_id)
    
    # Send response
    if file:
        await interaction.response.send_message(embed=embed, file=file, view=view, ephemeral=True)
    else:
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
    
    # Store active question
    active_questions[user_id] = {
        "question": question_data,
        "subject": subject,
        "view": view
    }

# Math practice command
@bot.tree.command(name="math_practice", description="Practice math questions")
@app_commands.choices(topic=[app_commands.Choice(name=name, value=name) for name in config.MATH_TOPICS])
async def math_practice(interaction: discord.Interaction, topic: app_commands.Choice[str]):
    await send_question(interaction, "math", topic.value)

# English practice command
@bot.tree.command(name="english_practice", description="Practice English questions")
@app_commands.choices(topic=[app_commands.Choice(name=name, value=name) for name in config.ENGLISH_TOPICS])
async def english_practice(interaction: discord.Interaction, topic: app_commands.Choice[str]):
    await send_question(interaction, "english", topic.value)

# Analytical practice command
@bot.tree.command(name="analytical_practice", description="Practice analytical questions")
@app_commands.choices(topic=[app_commands.Choice(name=name, value=name) for name in config.ANALYTICAL_TOPICS])
async def analytical_practice(interaction: discord.Interaction, topic: app_commands.Choice[str]):
    await send_question(interaction, "analytical", topic.value)

# Leaderboard command
@bot.tree.command(name="leaderboard", description="Show leaderboard")
async def leaderboard(interaction: discord.Interaction):
    leaderboard_data = await db.get_leaderboard(10)
    
    embed = discord.Embed(title="Leaderboard", color=discord.Color.gold())
    
    for i, (user_id, score) in enumerate(leaderboard_data[:10], 1):
        try:
            user = await bot.fetch_user(int(user_id))
            embed.add_field(name=f"{i}. {user.name}", value=f"Score: {score}", inline=False)
        except:
            embed.add_field(name=f"{i}. User {user_id}", value=f"Score: {score}", inline=False)
    
    await interaction.response.send_message(embed=embed)

# Profile command
@bot.tree.command(name="profile", description="Check your stats")
async def profile(interaction: discord.Interaction):
    user_id = interaction.user.id
    user_data = await db.get_user(user_id)
    
    embed = discord.Embed(title=f"{interaction.user.name}'s Profile", color=discord.Color.blue())
    embed.add_field(name="Total Score", value=user_data.get('total_score', 0), inline=False)
    embed.add_field(name="Questions Answered", value=user_data.get('questions_answered', 0), inline=False)
    
    await interaction.response.send_message(embed=embed)

# Run the bot
if __name__ == "__main__":
    bot.run(config.BOT_TOKEN)
