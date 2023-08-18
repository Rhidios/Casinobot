import discord
import asyncio
import random
import fetchinfo

from discord.ext import commands

bet_window_open = True
spin_result = None
spin_result_lock = asyncio.Lock()

intents = discord.Intents.all()

TOKEN = "MTEzNjQ1ODMwNTk5NzM4OTk2NA.Gkesan.tidGbYQPSbaDP1pkRVAO71hnPyjB48Dv2rgsqg"

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
    global spin_result
    global bet_window_open
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
        bet_window_open = False
        await asyncio.sleep(3)

        async with spin_result_lock:
            spin_result = roulette_game.spin()
            print(f"Roulette loop - spin_result: {spin_result}")
            result_message = await send_timed_message(channel, f"El número ganador es: {spin_result}")

        # Delete messages
        for msg in messages_to_delete:
            await msg.delete()

        bet_window_open = True


@bot.command(name='ruleta')
async def ruleta(ctx):
    global bet_window_open
    if not bet_window_open:
        await ctx.author.send("La ventana para apostar esta cerrada. Por favor aguarde a la siguiente ronda.")
        return

    user_id = str(ctx.author.id)

    # Load user credits from JSON
    credits_data = fetchinfo.load_credits()

    if user_id not in credits_data or credits_data[user_id] < 100:
        await ctx.author.send("No tiene suficientes creditos.")
        return

    roulette_game = RouletteGame()

    # Asking the user for their betting choice
    await ctx.author.send("Por favor escoja una opcion:\n"
                   "1. Numero\n"
                   "2. Color\n"
                   "3. Par/Impar\n"
                   "4. Columna\n"
                   "5. Docena")

    try:
        response = await bot.wait_for('message', timeout=60.0, check=lambda message: message.author == ctx.author)
        choice = response.content.lower()

        # Rest of the code for taking bets and processing them based on the chosen option
        if choice == '1':
            await ctx.author.send("Por favor ingrese el numero al que quiere apostar (1 a 36):")
            number_response = await bot.wait_for('message', timeout=60.0, check=lambda message: message.author == ctx.author)
            chosen_number = int(number_response.content)

            await ctx.author.send("Por favor ingrese el monto de la apuesta(maximo 500 creditos):")
            bet_amount_response = await bot.wait_for('message', timeout=60.0, check=lambda message: message.author == ctx.author)
            bet_amount = int(bet_amount_response.content)

            if bet_amount > 500:
                await ctx.author.send("La apuesta maxima para el pleno es de 500 creditos.")
                return

            if bet_amount > credits_data[user_id]:
                await ctx.author.send("No tienes suficientes creditos.")
                return

            async with spin_result_lock:
                print(f"Ruleta command - spin_result: {spin_result}")
                if chosen_number == spin_result:
                    winnings = bet_amount * 35
                    credits_data[user_id] += winnings
                    fetchinfo.save_credits(credits_data)
                    await ctx.author.send(f"Salió el {spin_result}. Felicidades! Has ganado {winnings} creditos!")
                else:
                    credits_data[user_id] -= bet_amount
                    fetchinfo.save_credits(credits_data)
                    await ctx.author.send(f"Salió el {spin_result}. Has perdido {bet_amount} creditos.")

        elif choice == '2':
            await ctx.send("Por favor escoja: Rojo o Negro:")
            color_response = await bot.wait_for('message', timeout=60.0, check=lambda message: message.author == ctx.author)
            chosen_color = color_response.content.lower()

            if chosen_color == 'red' and spin_result in roulette_game.red_numbers:
                await ctx.author.send(f"Ha salido {spin_result}. ¡Has ganado!")
            else: await ctx.author.send(f"Ha salido {spin_result}. Has perdido")
        # Add similar code blocks for other betting options (odd/even, column, dozen)

    except asyncio.TimeoutError:
        await ctx.author.send("You took too long to respond. Betting process canceled.")


bot.run(TOKEN)