import discord
import asyncio
import random
import json

from discord.ext import commands


intents = discord.Intents.all()

TOKEN = "MTEzNjQ1ODMwNTk5NzM4OTkyjB48Dv2rgsqg"

intents = discord.Intents().all()
client = discord.Client(intents = intents)
bot = commands.Bot(command_prefix='/', intents=intents)

class RouletteGame:
    def __init__(self):
        self.numbers = list(range(1, 37))
        self.red_numbers = [1, 3, 5, 7, 9, 12, 14, 16, 18, 19, 21, 23, 25, 27, 30, 32, 34, 36]
        self.black_numbers = [2, 4, 6, 8, 10, 11, 13, 15, 17, 20, 22, 24, 26, 28, 29, 31, 33, 35]
        self.dozen1 = list(range(1, 13))
        self.dozen2 = list(range(13, 25))
        self.dozen3 = list(range(25, 37))
        self.columns = [
            [1, 4, 7, 10, 13, 16, 19, 22, 25, 28, 31, 34],
            [2, 5, 8, 11, 14, 17, 20, 23, 26, 29, 32, 35],
            [3, 6, 9, 12, 15, 18, 21, 24, 27, 30, 33, 36]
        ]

    def spin(self):
        return random.choice(self.numbers)

@bot.event
async def on_ready():
    global roulette_game
    roulette_game = RouletteGame()
    bot.loop.create_task(roulette_loop())
    print(f'Logged in as {bot.user.name}')

async def send_timed_message(channel, content):
    message = await channel.send(content)
    return message

async def roulette_loop():
    channel_id = 607379812398661653

    while True:
        channel = bot.get_channel(channel_id)
        messages_to_delete = []

        timer_message = await send_timed_message(channel, "Quedan 60 segundos para la siguiente apuesta")
        await asyncio.sleep(10)
        messages_to_delete.append(timer_message)

        for remaining_time in range(20, 0, -10):
            message = await send_timed_message(channel, f"Quedan {remaining_time} segundos para cerrar la apuesta")
            messages_to_delete.append(message)
            await asyncio.sleep(10)  # Pause for 10 seconds before next loop iteration

        await send_timed_message(channel, "Apuestas cerradas. Espere a la siguiente vuelta")
        await asyncio.sleep(3)

        spin_result = roulette_game.spin()
        result_message = await send_timed_message(channel, f"El número ganador es: {spin_result}")

        # Delete messages
        for msg in messages_to_delete:
            await msg.delete()


bot.run(TOKEN)