import discord
import asyncio
import fetchinfo
import random
from PIL import Image

from discord.ext import commands
from discord import File


TOKEN = ""

intents = discord.Intents().all()
client = discord.Client(intents = intents)
bot = commands.Bot(command_prefix='/', intents=intents)

bet_window_open = True
spin_result = None
lock_bet = None
current_spin_result = None
spin_result_lock = asyncio.Lock()
spin_complete_event = asyncio.Event()

active_roulette_players = []

class RouletteGame:
    def __init__(self):
        self.numbers = list(range(0, 37))
        self.red_numbers = [1, 3, 5, 7, 9, 12, 14, 16, 18, 19, 21, 23, 25, 27, 30, 32, 34, 36]
        self.black_numbers = [2, 4, 6, 8, 10, 11, 13, 15, 17, 20, 22, 24, 26, 28, 29, 31, 33, 35]
        self.green_numbers = [0, 00]
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

    def get_color(self, number):
        if number in self.red_numbers:
            return "rojo"
        elif number in self.black_numbers:
            return "negro"
        elif number in self.green_numbers:
            return "verde"

    def is_even(self, number):
        return number % 2 == 0


welcome_message_id = None
@bot.event
async def on_ready():
    global roulette_game
    print(f'Logged in as {bot.user.name}')
    roulette_game = RouletteGame()
    bot.loop.create_task(roulette_loop())

@bot.event
async def on_member_join(member):
    global welcome_message_id
    welcome_channel_id = 1140535910572761138  # Replace with the actual welcome channel ID
    welcome_message = (f"**¡Bienvenido a Hubet Casino!** {member.mention}.\n"
                      f"Por favor solicita tu rol reaccionando y utiliza tu nombre IC para acceder al servidor.")

    channel = bot.get_channel(welcome_channel_id)
    message = await channel.send(welcome_message)
    welcome_message_id = message.id  # Store the message ID

    # Add a reaction to the message
    await message.add_reaction("🎉")  # You can use any emoji you like

@bot.event
async def on_raw_reaction_add(payload):
    global welcome_message_id
    if payload.member.bot:
        return

    if payload.channel_id == 1140535910572761138:  # Replace with the actual welcome channel ID
        if payload.message_id == welcome_message_id:  # Use 'payload.message_id' instead of 'payload.welcome_message_id'
            if str(payload.emoji) == "🎉":
                role_id = 1140540973609386086  # Replace with the actual role ID
                guild = bot.get_guild(payload.guild_id)
                role = guild.get_role(role_id)
                member = guild.get_member(payload.user_id)
                await member.add_roles(role)

# Command to check credits
@bot.command(name='wallet')
async def credits(ctx, target_member: discord.Member = None):
    if target_member is None:
        user_id = str(ctx.author.id)
        user_id_int = int(user_id)
        credits = fetchinfo.load_credits().get(user_id, 0)
        await ctx.send(f"Tienes {credits} creditos.")
        if user_id_int in active_blackjack_players:
            active_blackjack_players.remove(user_id_int)
    else:
        # Check if the user has the required role to view other users' wallets
        if any(role.name == 'Propietario' for role in ctx.author.roles):
            target_user_id = str(target_member.id)
            credits = fetchinfo.load_credits().get(target_user_id, 0)
            await ctx.send(f"{target_member.display_name} tiene {credits} creditos.")
        else:
            await ctx.send("No tienes permiso para verificar el saldo de otros usuarios.")

# Command to update credits (for roles with permission)
@bot.command(name='cargar')
@commands.has_role('Propietario')
async def give_credits(ctx, member_name: str, amount: int):
    member = discord.utils.find(lambda m: m.display_name.lower() == member_name.lower(), ctx.guild.members)

    if member:
        credits = fetchinfo.load_credits()
        member_id = str(member.id)
        print("Member ID:", member_id)
        print("Type of credits:", type(credits))
        credits = dict(credits)

        if member_id in credits:
            credits[member_id] += int(amount)
        else:
            credits[member_id] = int(amount)

        fetchinfo.save_credits(credits)

        await ctx.send(f"{amount} creditos han sido agregados a la cuenta de {member.display_name}.")
    else:
        await ctx.send("No se encontró un miembro con ese nombre.")

@bot.command(name='quitar')
@commands.has_role('Propietario')
async def take_credits(ctx, member_name: str, amount: int):
    member = discord.utils.find(lambda m: m.display_name.lower() == member_name.lower(), ctx.guild.members)
    if member:
        credits = fetchinfo.load_credits()
        member_id = str(member.id)
        credits[member_id] -= int(amount)

        fetchinfo.save_credits(credits)

        await ctx.send(f"{amount} creditos han sido retirados de la cuenta de {member.display_name}.")
    else:
        await ctx.send("No se encontró un miembro con ese nombre.")

# Dictionary of allowed max bets for different roles
max_bets = {
    'Regular Player': 20000,
    'Silver Player': 50000,
    'Golden Player': 100000,
    'Diamond Player': 250000,
    'Propietario': 1000000000000000000000000000000000000
}


async def send_formatted_message(channel, message):
    formatted_message = f"```\n{message}\n```"
    await channel.send(formatted_message)

active_blackjack_players = []


# Blackjack
@bot.command(name='blackjack')
@commands.has_any_role(*max_bets.keys()) #Roles with higher bet ceiling
async def blackjack(ctx):
    user_roles = [role.name for role in ctx.author.roles]
    suits = ['Corazones', 'Diamantes', 'Trebol', 'Picas']
    ranks = ['2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K', 'A']
    user_id = str(ctx.author.id)
    user_id_int = int(user_id)
    credits = fetchinfo.load_credits().get(user_id, 0)
    # Send a formatted message to the blackjack channel
    blackjack_channel = ctx.guild.get_channel(1145578107533787156)

    if credits <= 0:
        await ctx.send("No tienes suficientes créditos para jugar.")
        return

    if user_id_int in active_blackjack_players:
        await ctx.send("Ya estas jugando.")
        return

    active_blackjack_players.append(user_id_int)

    category = ctx.guild.get_channel(1140535910795071568)  # Replace with your category ID
    private_channel_name = f'blackjack-{ctx.author.name}'

    # Check if a channel with the same name already exists
    game_channel = discord.utils.get(category.text_channels, name=private_channel_name)

    if not game_channel:
        # Create a new channel if it doesn't exist
        game_channel = await category.create_text_channel(name=private_channel_name)

        # Grant necessary permissions to the author in the new channel
        member = ctx.author
        await game_channel.set_permissions(member, read_messages=True, send_messages=True, read_message_history=True)


    async def send_card_message(game_channel, cards):
        image_width = 150  # Adjust the desired width of each card image
        image_height = 220  # Adjust the desired height of each card image

        # Create a list to store card images
        card_images = []

        for card in cards:
            if ' de ' not in card:
                await game_channel.send(f"Invalid card format: {card}")
                return

            rank, suit = card.split(' de ')
            card_image = Image.open(f"cards/{rank.lower()}_of_{suit.lower()}.png")
            card_image = card_image.resize((image_width, image_height))
            card_images.append(card_image)

        # Create a new composite image to combine all card images
        composite_image = Image.new('RGBA', (image_width * len(card_images), image_height))

        # Paste each card image onto the composite image
        for i, card_image in enumerate(card_images):
            composite_image.paste(card_image, (i * image_width, 0))

        # Save the composite image
        composite_image.save('composite_cards.png')

        # Send the composite image as a file in a single message
        await game_channel.send(file=File('composite_cards.png'))

    # Move game-related messages to the new channel
    await game_channel.send(f"¡{ctx.author.mention}, bienvenido a la mesa de Blackjack en {game_channel.mention}!")
    await ctx.message.delete()

    # Create a list to store the cards from 6 decks
    decks = 6
    all_cards = []

    # Populate the all_cards list with cards from 6 decks
    for _ in range(decks):
        for suit in suits:
            for rank in ranks:
                card = f"{rank} de {suit}"
                all_cards.append(card)

    def calculate_hand_value(cards):
        value = 0
        num_aces = 0

        for card in cards:
            rank = card.split()[0]

            if rank in ['J', 'Q', 'K']:
                value += 10
            elif rank == 'A':
                num_aces += 1
                value += 11
            else:
                value += int(rank)

        # Adjust the value for aces
        while value > 21 and num_aces > 0:
            value -= 10
            num_aces -= 1

        return value
    while credits > 0:
        await game_channel.send(f"Actualmente tiene {credits} creditos. ¿Cuánto deseas apostar?")
        try:
            bet_message = await bot.wait_for('message', timeout=30.0, check=lambda message: message.author == ctx.author)
            bet = bet_message.content.lower()
            if bet == 'salir':
                await game_channel.send("Gracias por jugar en Hubet Casino")
                active_blackjack_players.remove(user_id_int)
                return
            else:
                bet = int(bet)
        except asyncio.TimeoutError:
            await game_channel.send("Tiempo de espera agotado. Vuelve a intentarlo.")
            active_blackjack_players.remove(user_id_int)
            return
        except ValueError:
            if user_id_int in active_blackjack_players:
                continue
            else:
                await game_channel.send("Cantidad inválida. Vuelve a intentarlo con un número entero.")
                continue

        for role_name in user_roles:
            if role_name in max_bets:
                if bet < 1000:
                    await game_channel.send("La apuesta minima es de $1000")
                elif bet > max_bets[role_name]:
                    await game_channel.send(f"Disculpa, {role_name} solo puede apostar hasta {max_bets[role_name]} creditos.")
                elif bet <= max_bets[role_name] and bet >= 1000:
                    if bet > credits:
                        await game_channel.send(f"No dispones de esa cantidad")
                    else:
                        await game_channel.send(f"Has apostado {bet} creditos")
                        bj_possible = False
                        # Shuffle the deck
                        random.shuffle(all_cards)
                        # Deal initial hands
                        player_hand = [all_cards.pop(), all_cards.pop()]
                        dealer_hand = [all_cards.pop(), all_cards.pop()]

                        player_value = calculate_hand_value(player_hand)
                        dealer_value = calculate_hand_value(dealer_hand)
    
                        if dealer_value == 21:
                            await game_channel.send("El dealer ha sacado Blackjack. ¡Perdiste!")
                            await send_formatted_message(blackjack_channel, f"¡Que pena!. {ctx.author.display_name} ha perdido {bet} creditos")
                            credits_data = fetchinfo.load_credits()
                            credits -= bet
                            credits_data[user_id] = credits
                            fetchinfo.save_credits(credits_data)
                            
                            if credits == 0:
                                await game_channel.send("No tiene mas creditos")
                                active_blackjack_players.remove(user_id_int)
                                return
                            else: continue

                        await send_card_message(game_channel, player_hand)
                        await game_channel.send(f"Tus cartas: {', '.join(player_hand)}. Tienes un total de {player_value}")
                        await send_card_message(game_channel, [dealer_hand[0]])
                        await game_channel.send(f"Carta visible del dealer: {dealer_hand[0]}. Tiene un total de {dealer_hand[0]}")
                        if player_value == 21:
                            # bet *= 2.25
                            await game_channel.send("¡Felicidades, has sacado un Blackjack!")
                            bj_possible = True
                            # Dealer's turn to draw cards
                            # Calculate dealer's hand value and determine the winner
                            dealer_value = calculate_hand_value(dealer_hand)
                            while dealer_value < 17:
                                new_card = all_cards.pop()
                                dealer_hand.append(new_card)
                                dealer_value = calculate_hand_value(dealer_hand)
                            await send_card_message(game_channel, dealer_hand)
                            await game_channel.send(f"Cartas del dealer: {', '.join(dealer_hand)}. Tiene un total de {dealer_value}")
                            if dealer_value > 21 or dealer_value < 21 and dealer_value >= 17:
                                bet *= 1.25
                                await game_channel.send(f"¡Felicidades, has ganado {bet}!")
                                await send_formatted_message(blackjack_channel, f"¡Felicidades!. {ctx.author.display_name} ha ganado {bet} creditos")
                                credits_data = fetchinfo.load_credits()
                                credits += bet
                                credits_data[user_id] = credits
                                fetchinfo.save_credits(credits_data)
                            elif dealer_value == 21:
                                await game_channel.send("¡Ha sido un empate!")
                                await send_formatted_message(blackjack_channel, f"{ctx.author.display_name} ha empatado con la casa.")
                                active_blackjack_players.remove(user_id_int)


                        # Game logic loop
                        while not bj_possible:
                            # Ask the player if they want to h or stand
                            await asyncio.sleep(1)
                            await game_channel.send("¿Quieres pedir carta (h), doblar (d) o quedarte (stand)? Responde 'h', 'd' o 's'.")
                            print("Waiting for response...")
                            try:
                                response = await bot.wait_for('message', timeout=300.0, check=lambda message: message.author == ctx.author and message.content.lower() in ['h', 'd', 's'])
                                action = response.content.strip().lower()
                                print("Message received:", response.content.strip().lower())
                            except asyncio.TimeoutError:
                                await game_channel.send("Tiempo de espera agotado. Vuelve a intentarlo.")
                                active_blackjack_players.remove(user_id_int)
                                return

                            if action == 'h':
                                new_card = all_cards.pop()
                                player_hand.append(new_card)
                                await game_channel.send(f"Nueva carta: {new_card}")
                                # Calculate player's hand value and check if it's over 21
                                player_value = calculate_hand_value(player_hand)
                                await send_card_message(game_channel, player_hand)
                                await game_channel.send(f"Tus cartas: {', '.join(player_hand)}. Tienes un total de {player_value}")
                                await game_channel.send(f"Carta visible del dealer: {dealer_hand[0]}. Tiene un total de {dealer_hand[0]}")
                                if player_value > 21:
                                    await game_channel.send("Has superado 21. ¡Perdiste!")
                                    await send_formatted_message(blackjack_channel, f"¡Que pena!. {ctx.author.display_name} ha perdido {bet} creditos")
                                    credits_data = fetchinfo.load_credits()
                                    credits -= bet
                                    credits_data[user_id] = credits
                                    fetchinfo.save_credits(credits_data)
                                    if credits == 0:
                                        await game_channel.send("No tiene mas creditos")
                                        active_blackjack_players.remove(user_id_int)
                                    break
                                if player_hand == 21:
                                    action == 's'

                            elif action == 'd':
                                if bet * 2 <= credits:
                                    bet *= 2
                                    new_card = all_cards.pop()
                                    player_hand.append(new_card)
                                    await game_channel.send(f"Nueva carta: {new_card}")
                                    # Calculate player's hand value and check if it's over 21
                                    player_value = calculate_hand_value(player_hand)
                                    await send_card_message(game_channel, player_hand)
                                    await game_channel.send(f"Tus cartas: {', '.join(player_hand)}. Tienes un total de {player_value}")
                                    if player_value > 21:
                                        await game_channel.send("Has superado 21. ¡Perdiste!")
                                        await send_formatted_message(blackjack_channel, f"¡Que pena!. {ctx.author.display_name} ha perdido {bet} creditos")
                                        credits_data = fetchinfo.load_credits()
                                        credits -= bet
                                        credits_data[user_id] = credits
                                        fetchinfo.save_credits(credits_data)
                                        if credits == 0:
                                            await game_channel.send("No tiene mas creditos")
                                            active_blackjack_players.remove(user_id_int)
                                        break
                                    if player_value <= 21:
                                        action = 's'
                                else:
                                    await game_channel.send("No tienes suficientes créditos para doblar la apuesta.")

                            if action == 's':
                                # Dealer's turn to draw cards
                                # Calculate dealer's hand value and determine the winner
                                dealer_value = calculate_hand_value(dealer_hand)
                                while dealer_value < 17:
                                    new_card = all_cards.pop()
                                    dealer_hand.append(new_card)
                                    dealer_value = calculate_hand_value(dealer_hand)
                                await send_card_message(game_channel, dealer_hand)
                                await game_channel.send(f"Cartas del dealer: {', '.join(dealer_hand)}. Tiene un total de {dealer_value}")

                                if dealer_value > 21:
                                    await game_channel.send(f"¡Felicidades, has ganado {bet}!")
                                    await send_formatted_message(blackjack_channel, f"¡Felicidades!. {ctx.author.display_name} ha ganado {bet} creditos")
                                    credits_data = fetchinfo.load_credits()
                                    credits += bet
                                    credits_data[user_id] = credits
                                    fetchinfo.save_credits(credits_data)
                                    break
                                elif dealer_value > player_value:
                                    await game_channel.send("¡Lo sentimos, has perdido!")
                                    await send_formatted_message(blackjack_channel, f"¡Que pena!. {ctx.author.display_name} ha perdido {bet} creditos")
                                    credits_data = fetchinfo.load_credits()
                                    credits -= bet
                                    credits_data[user_id] = credits
                                    fetchinfo.save_credits(credits_data)
                                    if credits == 0:
                                        await game_channel.send("No tiene mas creditos")
                                        active_blackjack_players.remove(user_id_int)
                                    break
                                elif dealer_value < player_value:
                                    await game_channel.send(f"¡Felicidades, has ganado {bet}!")
                                    await send_formatted_message(blackjack_channel, f"¡Felicidades!. {ctx.author.display_name} ha ganado {bet} creditos")
                                    credits_data = fetchinfo.load_credits()
                                    credits += bet
                                    credits_data[user_id] = credits
                                    fetchinfo.save_credits(credits_data)
                                    break
                                else:
                                    await game_channel.send("¡Ha sido un empate!")
                                    await send_formatted_message(blackjack_channel, f"{ctx.author.display_name} ha empatado con la casa.")
                                break

                else:
                    await game_channel.send(f"Disculpa, {role_name} solo puede apostar hasta {max_bets[role_name]} creditos.")


async def send_timed_message(channel, content):
    message = await channel.send(content)
    return message

async def send_image(channel, image_url):
    embed = discord.Embed()
    embed.set_image(url=image_url)
    return await channel.send(embed=embed)

async def roulette_loop():
    global spin_result
    global bet_window_open
    global current_spin_result
    channel_id = 1140535910795071577

    while True:
        channel = bot.get_channel(channel_id)
        messages_to_delete = []

        await asyncio.sleep(2)
        current_spin_result = None

        image_path = "roulette/roulette.png"
        image_file = discord.File(image_path)
        # Send the image as part of an embed
        embed = discord.Embed()
        embed.set_image(url=f"attachment://{image_path}")
        image_message = await channel.send(file=image_file, embed=embed)
        messages_to_delete.append(image_message)  # Append the image message object

        timer_message = await send_timed_message(channel, "Quedan 60 segundos para la siguiente apuesta")
        await asyncio.sleep(10)
        messages_to_delete.append(timer_message)

        for remaining_time in range(50, 0, -10):
            message = await send_timed_message(channel, f"Quedan {remaining_time} segundos para cerrar la apuesta")
            messages_to_delete.append(message)
            await asyncio.sleep(10)  # Pause for 10 seconds before next loop iteration

        close_message = await send_timed_message(channel, "Apuestas cerradas. Espere a la siguiente vuelta")
        messages_to_delete.append(close_message)
        bet_window_open = False
        await asyncio.sleep(1)
        stop_message = await channel.send("*Esperando que la bola se detenga...*")
        # Send the GIF here
        gif_path = "roulette/gXYMAo.gif"  # Replace with the actual path to your GIF
        gif_message = await channel.send(file=discord.File(gif_path))
        messages_to_delete.append(gif_message)  # Append the GIF message object

        messages_to_delete.append(stop_message)
        await asyncio.sleep(5)

        async with spin_result_lock:
            spin_result = roulette_game.spin()
            current_spin_result = spin_result
            spin_color = roulette_game.get_color(spin_result)
            print(f"Roulette loop - spin_result: {spin_result}")
            result_message = await send_timed_message(channel, f"**El número ganador es: {spin_result} {spin_color}**")
            await asyncio.sleep(2)
            reset_message = await channel.send("Limpiando apuestas... Por favor aguarden a la siguiente ronda.")
            messages_to_delete.append(reset_message)
            await asyncio.sleep(5)

        # Delete messages
        for msg in messages_to_delete:
            await msg.delete()

        bet_window_open = True
        spin_complete_event.set()  # Set the event to signal that the spin is complete

        # Wait for the spin to complete before proceeding to the next iteration
        await spin_complete_event.wait()

async def send_formatted_message(channel, message):
    formatted_message = f"```\n{message}\n```"
    await channel.send(formatted_message)

@bot.command(name='ruleta')
# @commands.has_any_role(*max_bets.keys())
async def ruleta(ctx):
    global bet_window_open
    global lock_bet
    global current_spin_result
    user_id = str(ctx.author.id)
    user_id_int = int(user_id)
    roulette_channel = ctx.guild.get_channel(1140535910795071577)

    await ctx.message.delete()

    category = ctx.guild.get_channel(1140535910795071568)  # Replace with your category ID
    private_channel_name = f'ruleta-{ctx.author.name}'

    # Check if a channel with the same name already exists
    game_channel = discord.utils.get(category.text_channels, name=private_channel_name)

    if not game_channel:
        # Create a new channel if it doesn't exist
        game_channel = await category.create_text_channel(name=private_channel_name)

        # Grant necessary permissions to the author in the new channel
        member = ctx.author
        await game_channel.set_permissions(member, read_messages=True, send_messages=True, read_message_history=True)

        # Move game-related messages to the new channel
        await game_channel.send(f"¡{ctx.author.mention}, bienvenido a la mesa de apuestas de ruleta en {game_channel.mention}!")


    if not bet_window_open:
        await game_channel.send("La ventana para apostar esta cerrada. Por favor aguarde a la siguiente ronda.")
        return

    if user_id_int in active_roulette_players:
        await game_channel.send("Ya estas jugando.")
        return

    active_roulette_players.append(user_id_int)

    # Load user credits from JSON
    credits_data = fetchinfo.load_credits()

    if user_id not in credits_data or credits_data[user_id] < 100:
        await game_channel.send("No tiene suficientes creditos.")
        return

    roulette_game = RouletteGame()
    # Asking the user for their betting choice
    while True:
        image_path = "roulette/roulette.png"
        image_file = discord.File(image_path)
        # Send the image as part of an embed
        embed = discord.Embed()
        embed.set_image(url=f"attachment://{image_path}")
        image_message = await game_channel.send(file=image_file, embed=embed)

        bet = await game_channel.send("Por favor escoja una opcion:\n"
                    "1. Numero\n"
                    "2. Color\n"
                    "3. Par/Impar\n"
                    "4. Columna\n"
                    "5. Docena\n"
                    "0. Salir")

        if bet_window_open == False:
            await game_channel.send("La ventana para apuestas ha cerrado. Espera a la siguiente ronda")
            active_roulette_players.remove(user_id_int)
            print("Deleted active r players")
            return
        if current_spin_result is not None:  # Check if there's a current spin result
            await game_channel.send("La ventana de apuesta anterior ha cerrado. Haz /ruleta nuevamente en el canal de ruleta.")
            active_roulette_players.remove(user_id_int)
            print("Deleted active r players")
            return

        try:
            response = await bot.wait_for('message', timeout=60.0, check=lambda message: message.author == ctx.author)
            choice = response.content.lower()

            if choice == '0':
                await game_channel.send("Gracias por jugar en Hubet Casino")
                active_roulette_players.remove(user_id_int)
                print("Deleted active r players")
                return

            # Rest of the code for taking bets and processing them based on the chosen option
            if choice == '1':
                while True:
                    await game_channel.send("Ingrese el numero al que quiere apostar (1 a 36):")
                    number_response = await bot.wait_for('message', timeout=10.0, check=lambda message: message.author == ctx.author)
                    try:
                        chosen_number = int(number_response.content)
                        if bet_window_open == False:
                            await game_channel.send("La ventana para apuestas ha cerrado. Espera a la siguiente ronda")
                            active_roulette_players.remove(user_id_int)
                            print("Deleted active r players")
                            return
                        if current_spin_result is not None:  # Check if there's a current spin result
                            await game_channel.send("La ventana de apuesta anterior ha cerrado. Haz /ruleta nuevamente en el canal de ruleta.")
                            active_roulette_players.remove(user_id_int)
                            print("Deleted active r players")
                            return
                        if chosen_number < 1 or chosen_number > 36:
                            await game_channel.send("Por favor escoja un número del 1 al 36")
                            continue  # Continue the loop if the number is invalid
                        else:
                            break  # Break the loop if the number is valid
                    except asyncio.TimeoutError:
                        await game_channel.send("Tiempo de espera agotado. Vuelve a intentarlo.")
                        active_roulette_players.remove(user_id_int)
                        print("Deleted active r players")
                        return
                    except ValueError:
                        await game_channel.send("Por favor ingrese un número válido")
                        continue  # Continue the loop if there's a value error

                while True:
                    while True:
                        await game_channel.send("Por favor ingrese el monto de la apuesta(min 100. max 500):")
                        bet_amount_response = await bot.wait_for('message', timeout=10.0, check=lambda message: message.author == ctx.author)
                        try:
                            bet_amount = int(bet_amount_response.content)
                            if bet_window_open == False:
                                await game_channel.send("La ventana para apuestas ha cerrado. Espera a la siguiente ronda")
                                active_roulette_players.remove(user_id_int)
                                print("Deleted active r players")
                                return
                            if current_spin_result is not None:  # Check if there's a current spin result
                                await game_channel.send("La ventana de apuesta anterior ha cerrado. Haz /ruleta nuevamente en el canal de ruleta.")
                                active_roulette_players.remove(user_id_int)
                                print("Deleted active r players")
                                return
                            if bet_amount < 100 or bet_amount > 500:
                                await game_channel.send("La minima es de 100 y la maxima de 500 para el pleno.")
                                continue

                            if bet_amount > credits_data[user_id]:
                                await game_channel.send("No tienes suficientes creditos.")
                                continue
                            else: break
                        except ValueError:
                            await game_channel.send("Por favor ingresa un numero")
                            continue
                    while True:
                        if bet_window_open:
                            await game_channel.send("Apuesta registrada. Por favor aguarde al resultado")
                            lock_bet = True
                            active_roulette_players.remove(user_id_int)
                            print("Deleted active r players")
                            await spin_complete_event.wait()  # Wait for the event to be set
                            spin_complete_event.clear()  # Clear the event for the next spin

                            async with spin_result_lock:
                                print(f"Ruleta command - spin_result: {spin_result}")
                                if chosen_number == spin_result:
                                    winnings = bet_amount * 35
                                    credits_data[user_id] += winnings
                                    fetchinfo.save_credits(credits_data)
                                    await game_channel.send(f"Salió el {spin_result}. Felicidades! Has ganado {winnings} creditos!")
                                    await send_formatted_message(roulette_channel, f"¡Felicidades!. {ctx.author.display_name} ha ganado {winnings} creditos apostando al {chosen_number}")
                                    return
                                else:
                                    credits_data[user_id] -= bet_amount
                                    fetchinfo.save_credits(credits_data)
                                    await game_channel.send(f"Salió el {spin_result}. Has perdido {bet_amount} creditos.")
                                    await send_formatted_message(roulette_channel, f"{ctx.author.display_name} ha perdido {bet_amount} creditos apostando al {chosen_number}")
                                    if credits == 0:
                                        await game_channel.send("No tiene mas creditos")
                                        active_roulette_players.remove(user_id_int)
                                        print("Deleted active r players")
                                    return
                        else:
                            await game_channel.send("La ventana para apuestas ha cerrado.")
                            active_roulette_players.remove(user_id_int)
                            print("Deleted active r players")
                            return  # Exit the function and stop processing bets

            elif choice == '2':
                while True:
                    await game_channel.send("Escoja: Rojo o Negro:")
                    color_response = await bot.wait_for('message', timeout=10.0, check=lambda message: message.author == ctx.author)
                    try:
                        colors = ['rojo','negro']
                        chosen_color = color_response.content.lower()
                        if bet_window_open == False:
                            await game_channel.send("La ventana para apuestas ha cerrado. Espera a la siguiente ronda")
                            active_roulette_players.remove(user_id_int)
                            print("Deleted active r players")
                            return
                        if current_spin_result is not None:  # Check if there's a current spin result
                            await game_channel.send("La ventana de apuesta anterior ha cerrado. Haz /ruleta nuevamente en el canal de ruleta.")
                            active_roulette_players.remove(user_id_int)
                            print("Deleted active r players")
                            return
                        if chosen_color not in colors:
                            await game_channel.send("Por favor escoja rojo o negro")
                            continue  # Continue the loop if the number is invalid
                        else:
                            break  # Break the loop if the number is valid
                    except ValueError:
                        await game_channel.send("Por favor escoja rojo o negro")
                        continue  # Continue the loop if there's a value error
                while True:
                    while True:
                        await game_channel.send("Por favor ingrese el monto de la apuesta (min 1000. max 3000):")
                        bet_amount_response = await bot.wait_for('message', timeout=10.0, check=lambda message: message.author == ctx.author)
                        try:
                            bet_amount = int(bet_amount_response.content)
                            if bet_window_open == False:
                                await game_channel.send("La ventana para apuestas ha cerrado. Espera a la siguiente ronda")
                                active_roulette_players.remove(user_id_int)
                                print("Deleted active r players")
                                return
                            if current_spin_result is not None:  # Check if there's a current spin result
                                await game_channel.send("La ventana de apuesta anterior ha cerrado. Haz /ruleta nuevamente en el canal de ruleta.")
                                active_roulette_players.remove(user_id_int)
                                print("Deleted active r players")
                                return
                            if bet_amount < 1000 or bet_amount > 3000:
                                await game_channel.send("La minima es de 1000 y la maxima de 3000 para el color.")
                                continue
                            if bet_amount > credits_data[user_id]:
                                await game_channel.send("No tienes suficientes creditos.")
                                continue
                            else: break
                        except ValueError:
                            await game_channel.send("Por favor ingresa un numero")
                            continue

                    while True:
                        if bet_window_open:
                            await game_channel.send("Apuesta registrada. Por favor aguarde al resultado")
                            lock_bet = True
                            active_roulette_players.remove(user_id_int)
                            print("Deleted active r players")
                            await spin_complete_event.wait()  # Wait for the event to be set
                            spin_complete_event.clear()  # Clear the event for the next spin

                            async with spin_result_lock:
                                if chosen_color == 'rojo' and spin_result in roulette_game.red_numbers:
                                    winnings = bet_amount
                                    credits_data[user_id] += winnings
                                    fetchinfo.save_credits(credits_data)
                                    await game_channel.send(f"Salió el {spin_result}. Felicidades! Has ganado {winnings} creditos!")
                                    await send_formatted_message(roulette_channel, f"¡Felicidades!. {ctx.author.display_name} ha ganado {winnings} creditos apostando al {chosen_color}")
                                    return
                                # elif chosen_color == 'rojo' and spin_result in roulette_game.black_numbers:
                                #     credits_data[user_id] -= bet_amount
                                #     fetchinfo.save_credits(credits_data)
                                #     await game_channel.send(f"Salió el {spin_result}. Has perdido {bet_amount} creditos.")
                                #     credits_data[user_id] -= bet_amount
                                #     await send_formatted_message(roulette_channel, f"{ctx.author.display_name} ha perdido {bet_amount} creditos apostando al {chosen_color}")
                                elif chosen_color == 'negro' and spin_result in roulette_game.black_numbers:
                                    winnings = bet_amount
                                    credits_data[user_id] += winnings
                                    fetchinfo.save_credits(credits_data)
                                    await game_channel.send(f"Salió el {spin_result}. Felicidades! Has ganado {winnings} creditos!")
                                    await send_formatted_message(roulette_channel, f"¡Felicidades!. {ctx.author.display_name} ha ganado {winnings} creditos apostando al {chosen_color}")
                                    return
                                # elif chosen_color == 'negro' and spin_result in roulette_game.red_numbers:
                                #     credits_data[user_id] -= bet_amount
                                #     fetchinfo.save_credits(credits_data)
                                #     await game_channel.send(f"Salió el {spin_result}. Has perdido {bet_amount} creditos.")
                                #     await send_formatted_message(roulette_channel, f"{ctx.author.display_name} ha perdido {bet_amount} creditos apostando al {chosen_color}")
                                elif spin_result in roulette_game.green_numbers:
                                    credits_data[user_id] -= bet_amount
                                    fetchinfo.save_credits(credits_data)
                                    await game_channel.send(f"Salió el {spin_result}. Has perdido {bet_amount} creditos.")
                                    await send_formatted_message(roulette_channel, f"{ctx.author.display_name} ha perdido {bet_amount} creditos apostando al {chosen_color}")
                                    return
                                else:
                                    credits_data[user_id] -= bet_amount
                                    fetchinfo.save_credits(credits_data)
                                    await game_channel.send(f"Salió el {spin_result}. Has perdido {bet_amount} creditos.")
                                    await send_formatted_message(roulette_channel, f"{ctx.author.display_name} ha perdido {bet_amount} creditos apostando al {chosen_color}")
                                    return
                        else:
                            await game_channel.send("La ventana para apuestas ha cerrado.")
                            active_roulette_players.remove(user_id_int)
                            print("Deleted active r players")
                            return  # Exit the function and stop processing bets
            # Add similar code blocks for other betting options (odd/even, column, dozen)
            elif choice == '3':
                while True:
                    await game_channel.send("Escoja: Par o Impar:")
                    even_odd_response = await bot.wait_for('message', timeout=10.0, check=lambda message: message.author == ctx.author)
                    try:
                        even_odd = ['par','impar']
                        chosen_even_odd = even_odd_response.content.lower()
                        if bet_window_open == False:
                            await game_channel.send("La ventana para apuestas ha cerrado. Espera a la siguiente ronda")
                            active_roulette_players.remove(user_id_int)
                            print("Deleted active r players")
                            return
                        if current_spin_result is not None:  # Check if there's a current spin result
                            await game_channel.send("La ventana de apuesta anterior ha cerrado. Haz /ruleta nuevamente en el canal de ruleta.")
                            active_roulette_players.remove(user_id_int)
                            print("Deleted active r players")
                            return
                        if chosen_even_odd not in even_odd:
                            await game_channel.send("Por favor escoja Par o Impar")
                            continue  # Continue the loop if the number is invalid
                        else:
                            break  # Break the loop if the number is valid
                    except ValueError:
                        await game_channel.send("Por favor escoja Par o Impar")
                        continue  # Continue the loop if there's a value error

                while True:
                    while True:
                        await game_channel.send("Por favor ingrese el monto de la apuesta (min 1000. max 3000):")
                        bet_amount_response = await bot.wait_for('message', timeout=10.0, check=lambda message: message.author == ctx.author)
                        try:
                            bet_amount = int(bet_amount_response.content)
                            if bet_window_open == False:
                                await game_channel.send("La ventana para apuestas ha cerrado. Espera a la siguiente ronda")
                                active_roulette_players.remove(user_id_int)
                                print("Deleted active r players")
                                return
                            if current_spin_result is not None:  # Check if there's a current spin result
                                await game_channel.send("La ventana de apuesta anterior ha cerrado. Haz /ruleta nuevamente en el canal de ruleta.")
                                active_roulette_players.remove(user_id_int)
                                print("Deleted active r players")
                                return
                            if bet_amount < 1000 or bet_amount > 3000:
                                await game_channel.send("La minima es de 1000 y la maxima de 3000 para el color.")
                                continue
                            if bet_amount > credits_data[user_id]:
                                await game_channel.send("No tienes suficientes creditos.")
                                continue
                            else: break
                        except ValueError:
                            await game_channel.send("Por favor ingresa un numero entre 1000 y 3000")
                            continue

                    while True:
                        if bet_window_open:
                            await game_channel.send("Apuesta registrada. Por favor aguarde al resultado")
                            lock_bet = True
                            active_roulette_players.remove(user_id_int)
                            await spin_complete_event.wait()  # Wait for the event to be set
                            spin_complete_event.clear()  # Clear the event for the next spin

                            async with spin_result_lock:
                                # Calculate the winnings or losses based on even/odd result
                                if chosen_even_odd == 'par' and roulette_game.is_even(spin_result):
                                    winnings = bet_amount
                                    credits_data[user_id] += winnings
                                    fetchinfo.save_credits(credits_data)
                                    await game_channel.send(f"Salió el {spin_result}. Felicidades! Has ganado {winnings} creditos!")
                                    await send_formatted_message(roulette_channel, f"¡Felicidades!. {ctx.author.display_name} ha ganado {winnings} creditos apostando a {chosen_even_odd}")
                                    return
                                elif chosen_even_odd == 'impar' and not roulette_game.is_even(spin_result):
                                    winnings = bet_amount
                                    credits_data[user_id] += winnings
                                    fetchinfo.save_credits(credits_data)
                                    await game_channel.send(f"Salió el {spin_result}. Felicidades! Has ganado {winnings} creditos!")
                                    await send_formatted_message(roulette_channel, f"¡Felicidades!. {ctx.author.display_name} ha ganado {winnings} creditos apostando a {chosen_even_odd}")
                                    return
                                else:
                                    credits_data[user_id] -= bet_amount
                                    fetchinfo.save_credits(credits_data)
                                    await game_channel.send(f"Salió el {spin_result}. Has perdido {bet_amount} creditos.")
                                    await send_formatted_message(roulette_channel, f"{ctx.author.display_name} ha perdido {bet_amount} creditos apostando a {chosen_even_odd}")
                                    return
                        else:
                            await game_channel.send("La ventana para apuestas ha cerrado.")
                            active_roulette_players.remove(user_id_int)
                            print("Deleted active r players")
                            return  # Exit the function and stop processing bets

            elif choice == '4':
                while True:
                    await game_channel.send("Escoja 1era(1), 2da(2), o 3ra columna(3):")
                    column_response = await bot.wait_for('message', timeout=10.0, check=lambda message: message.author == ctx.author)
                    try:
                        columns = ['1','2','3']
                        chosen_column = column_response.content.lower()
                        if bet_window_open == False:
                            await game_channel.send("La ventana para apuestas ha cerrado. Espera a la siguiente ronda")
                            active_roulette_players.remove(user_id_int)
                            print("Deleted active r players")
                            return
                        if current_spin_result is not None:  # Check if there's a current spin result
                            await game_channel.send("La ventana de apuesta anterior ha cerrado. Haz /ruleta nuevamente en el canal de ruleta.")
                            active_roulette_players.remove(user_id_int)
                            print("Deleted active r players")
                            return
                        if chosen_column not in columns:
                            await game_channel.send("Por favor escoja Par o Impar")
                            continue  # Continue the loop if the number is invalid
                        else:
                            break  # Break the loop if the number is valid
                    except ValueError:
                        await game_channel.send("Por favor escoja Par o Impar")
                        continue  # Continue the loop if there's a value error

                while True:
                    while True:
                        await game_channel.send("Por favor ingrese el monto de la apuesta (min 1000. max 3000):")
                        bet_amount_response = await bot.wait_for('message', timeout=10.0, check=lambda message: message.author == ctx.author)
                        try:
                            bet_amount = int(bet_amount_response.content)
                            if bet_window_open == False:
                                await game_channel.send("La ventana para apuestas ha cerrado. Espera a la siguiente ronda")
                                active_roulette_players.remove(user_id_int)
                                print("Deleted active r players")
                                return
                            if current_spin_result is not None:  # Check if there's a current spin result
                                await game_channel.send("La ventana de apuesta anterior ha cerrado. Haz /ruleta nuevamente en el canal de ruleta.")
                                active_roulette_players.remove(user_id_int)
                                print("Deleted active r players")
                                return
                            if bet_amount < 1000 or bet_amount > 3000:
                                await game_channel.send("La minima es de 1000 y la maxima de 3000 para el color.")
                                continue
                            if bet_amount > credits_data[user_id]:
                                await game_channel.send("No tienes suficientes creditos.")
                                continue
                            else: break
                        except ValueError:
                            await game_channel.send("Por favor ingresa un numero entre 1000 y 3000")
                            continue

                    while True:
                        if bet_window_open:
                            await game_channel.send("Apuesta registrada. Por favor aguarde al resultado")
                            lock_bet = True
                            active_roulette_players.remove(user_id_int)
                            await spin_complete_event.wait()  # Wait for the event to be set
                            spin_complete_event.clear()  # Clear the event for the next spin

                            async with spin_result_lock:
                                # Calculate the winnings or losses based on even/odd result
                                if chosen_column == '1' and spin_result in roulette_game.columns[0]:
                                    winnings = bet_amount * 1.25
                                    credits_data[user_id] += winnings
                                    fetchinfo.save_credits(credits_data)
                                    await game_channel.send(f"Salió el {spin_result}. Felicidades! Has ganado {winnings} creditos!")
                                    await send_formatted_message(roulette_channel, f"¡Felicidades!. {ctx.author.display_name} ha ganado {winnings} creditos apostando a la columna {chosen_column}")
                                    return
                                elif chosen_column == '2' and spin_result in roulette_game.columns[1]:
                                    winnings = bet_amount * 1.25
                                    credits_data[user_id] += winnings
                                    fetchinfo.save_credits(credits_data)
                                    await game_channel.send(f"Salió el {spin_result}. Felicidades! Has ganado {winnings} creditos!")
                                    await send_formatted_message(roulette_channel, f"¡Felicidades!. {ctx.author.display_name} ha ganado {winnings} creditos apostando a la columna {chosen_column}")
                                    return
                                elif chosen_column == '3' and spin_result in roulette_game.columns[2]:
                                    winnings = bet_amount * 1.25
                                    credits_data[user_id] += winnings
                                    fetchinfo.save_credits(credits_data)
                                    await game_channel.send(f"Salió el {spin_result}. Felicidades! Has ganado {winnings} creditos!")
                                    await send_formatted_message(roulette_channel, f"¡Felicidades!. {ctx.author.display_name} ha ganado {winnings} creditos apostando a la columna {chosen_column}")
                                    return
                                else:
                                    credits_data[user_id] -= bet_amount
                                    fetchinfo.save_credits(credits_data)
                                    await game_channel.send(f"Salió el {spin_result}. Has perdido {bet_amount} creditos.")
                                    await send_formatted_message(roulette_channel, f"{ctx.author.display_name} ha perdido {bet_amount} creditos apostando a la columna {chosen_column}")
                                    return
                        else:
                            await game_channel.send("La ventana para apuestas ha cerrado.")
                            active_roulette_players.remove(user_id_int)
                            print("Deleted active r players")
                            return  # Exit the function and stop processing bets

            elif choice == '5':
                while True:
                    await game_channel.send("Escoja 1era(1), 2da(2), o 3ra docena(3):")
                    dozen_response = await bot.wait_for('message', timeout=10.0, check=lambda message: message.author == ctx.author)
                    try:
                        dozens = ['1','2','3']
                        chosen_dozen = dozen_response.content.lower()
                        if bet_window_open == False:
                            await game_channel.send("La ventana para apuestas ha cerrado. Espera a la siguiente ronda")
                            active_roulette_players.remove(user_id_int)
                            print("Deleted active r players")
                            return
                        if current_spin_result is not None:  # Check if there's a current spin result
                            await game_channel.send("La ventana de apuesta anterior ha cerrado. Haz /ruleta nuevamente en el canal de ruleta.")
                            active_roulette_players.remove(user_id_int)
                            print("Deleted active r players")
                            return
                        if chosen_dozen not in dozens:
                            await game_channel.send("Por favor escoja 1, 2, o 3")
                            continue  # Continue the loop if the number is invalid
                        else:
                            break  # Break the loop if the number is valid
                    except ValueError:
                        await game_channel.send("Por favor escoja 1, 2, o 3")
                        continue  # Continue the loop if there's a value error

                while True:
                    while True:
                        await game_channel.send("Por favor ingrese el monto de la apuesta (min 1000. max 3000):")
                        bet_amount_response = await bot.wait_for('message', timeout=10.0, check=lambda message: message.author == ctx.author)
                        try:
                            bet_amount = int(bet_amount_response.content)
                            if bet_window_open == False:
                                await game_channel.send("La ventana para apuestas ha cerrado. Espera a la siguiente ronda")
                                active_roulette_players.remove(user_id_int)
                                print("Deleted active r players")
                                return
                            if current_spin_result is not None:  # Check if there's a current spin result
                                await game_channel.send("La ventana de apuesta anterior ha cerrado. Haz /ruleta nuevamente en el canal de ruleta.")
                                active_roulette_players.remove(user_id_int)
                                print("Deleted active r players")
                                return
                            if bet_amount < 1000 or bet_amount > 3000:
                                await game_channel.send("La minima es de 1000 y la maxima de 3000 para el color.")
                                continue
                            if bet_amount > credits_data[user_id]:
                                await game_channel.send("No tienes suficientes creditos.")
                                continue
                            else: break
                        except ValueError:
                            await game_channel.send("Por favor ingresa un numero entre 1000 y 5000")
                            continue

                    while True:
                        if bet_window_open:
                            await game_channel.send("Apuesta registrada. Por favor aguarde al resultado")
                            lock_bet = True
                            active_roulette_players.remove(user_id_int)
                            await spin_complete_event.wait()  # Wait for the event to be set
                            spin_complete_event.clear()  # Clear the event for the next spin

                            async with spin_result_lock:
                                # Calculate the winnings or losses based on even/odd result
                                if chosen_dozen == '1' and spin_result in roulette_game.dozen1:
                                    winnings = bet_amount
                                    credits_data[user_id] += winnings
                                    fetchinfo.save_credits(credits_data)
                                    await game_channel.send(f"Salió el {spin_result}. Felicidades! Has ganado {winnings} creditos!")
                                    await send_formatted_message(roulette_channel, f"¡Felicidades!. {ctx.author.display_name} ha ganado {winnings} creditos apostando a la columna {chosen_dozen}")
                                    return
                                elif chosen_dozen == '2' and spin_result in roulette_game.dozen2:
                                    winnings = bet_amount
                                    credits_data[user_id] += winnings
                                    fetchinfo.save_credits(credits_data)
                                    await game_channel.send(f"Salió el {spin_result}. Felicidades! Has ganado {winnings} creditos!")
                                    await send_formatted_message(roulette_channel, f"¡Felicidades!. {ctx.author.display_name} ha ganado {winnings} creditos apostando a la columna {chosen_dozen}")
                                    return
                                elif chosen_dozen == '3' and spin_result in roulette_game.dozen3:
                                    winnings = bet_amount
                                    credits_data[user_id] += winnings
                                    fetchinfo.save_credits(credits_data)
                                    await game_channel.send(f"Salió el {spin_result}. Felicidades! Has ganado {winnings} creditos!")
                                    await send_formatted_message(roulette_channel, f"¡Felicidades!. {ctx.author.display_name} ha ganado {winnings} creditos apostando a la columna {chosen_dozen}")
                                    return
                                else:
                                    credits_data[user_id] -= bet_amount
                                    fetchinfo.save_credits(credits_data)
                                    await game_channel.send(f"Salió el {spin_result}. Has perdido {bet_amount} creditos.")
                                    await send_formatted_message(roulette_channel, f"{ctx.author.display_name} ha perdido {bet_amount} creditos apostando a la columna {chosen_dozen}")
                                    return
                        else:
                            await game_channel.send("La ventana para apuestas ha cerrado.")
                            active_roulette_players.remove(user_id_int)
                            print("Deleted active r players")
                            return  # Exit the function and stop processing bets

        except asyncio.TimeoutError:
            await game_channel.send("Has tardado demasiado en responder.Apuesta cerrada.")
            active_roulette_players.remove(user_id_int)
            print("Deleted active r players")
            return
        except ValueError:
            if user_id_int in active_roulette_players:
                continue
            else:
                await game_channel.send("Escoja un numero entre las opciones.")
                continue

slot_icons = ["🍒", "🍊", "🍇", "🍀", "🔔", "💎"]
num_columns = 5
num_rows = 5
spin_duration = 3  # seconds
spin_frames = 10
frame_delay = spin_duration / spin_frames

winning_combinations = [
    ["🍒", "🍒", "🍒"],["🍒", "🍒", "🍒", "🍒"],["🍒", "🍒", "🍒", "🍒", "🍒"],
    ["🍊", "🍊", "🍊"],["🍊", "🍊", "🍊", "🍊"],["🍊", "🍊", "🍊", "🍊", "🍊"],
    ["🍇", "🍇", "🍇"],["🍇", "🍇", "🍇", "🍇"],["🍇", "🍇", "🍇", "🍇", "🍇"],
    ["🍀", "🍀", "🍀"],["🍀", "🍀", "🍀", "🍀"],["🍀", "🍀", "🍀", "🍀", "🍀"],
    ["🔔", "🔔", "🔔"],["🔔", "🔔", "🔔", "🔔"],["🔔", "🔔", "🔔", "🔔", "🔔"],
    ["💎", "💎", "💎"],["💎", "💎", "💎", "💎"],["💎", "💎", "💎", "💎", "💎"]
]

async def check_win(results):
    payout_multiplier = 0
    winning_combos = []  # Store the winning combos

    def check_consecutive(lst, icon, count):
        for i in range(len(lst) - count + 1):
            if all(lst[i + j] == icon for j in range(count)):
                return True
        return False

    # Check rows for wins
    for row in range(num_rows):
        for combo in winning_combinations:
            row_values = [results[col][row] for col in range(num_columns)]  # Adjust indexing here
            if check_consecutive(row_values, combo[0], len(combo)):
                combo_length = len(combo)
                if combo_length == 3:
                    payout_multiplier += 0.5
                elif combo_length == 4:
                    payout_multiplier += 1.5
                elif combo_length == 5:
                    payout_multiplier += 3
                winning_combos.append([f"row {row + 1}, col {col + 1}" for col in range(num_columns) if results[col][row] == combo[0]])  # Adjust indexing here

     # Check diagonals for wins (both directions)
    for row in range(num_rows):
        for col in range(num_columns):
            for combo in winning_combinations:
                # Check diagonal from top-left to bottom-right
                diagonal_values1 = [results[col + i][row + i] if 0 <= col + i < num_columns and 0 <= row + i < num_rows else None for i in range(len(combo))]
                # Check diagonal from top-right to bottom-left
                diagonal_values2 = [results[col + i][row - i] if 0 <= col + i < num_columns and 0 <= row - i < num_rows else None for i in range(len(combo))]
                if (None not in diagonal_values1 and check_consecutive(diagonal_values1, combo[0], len(combo))) or (None not in diagonal_values2 and check_consecutive(diagonal_values2, combo[0], len(combo))):
                    combo_length = len(combo)
                    if combo_length == 3:
                        payout_multiplier += 0.5
                    elif combo_length == 4:
                        payout_multiplier += 1.5
                    elif combo_length == 5:
                        payout_multiplier += 3
                    winning_combos.append([f"col {col + i + 1}, row {row + i + 1}" for i in range(len(combo)) if results[col + i][row + i] == combo[0]])

    print("Winning Combos:")
    for combo in winning_combos:
        print(combo)

    return payout_multiplier

max_slots_bets = {
    'Regular Player': 1000,
    'Silver Player': 2500,
    'Golden Player': 5000,
    'Diamond Player': 10000,
    'Propietario': 1000000000000000000000000000000000000
}

async def run_slots(ctx, bet_amount):
    user_roles = [role.name for role in ctx.author.roles]
    user_id = str(ctx.author.id)
    user_id_int = int(user_id)
    credits = fetchinfo.load_credits().get(user_id, 0)
    bet_amount = float(bet_amount)
    credits -= bet_amount

    slots_channel = ctx.guild.get_channel(1145579311215157248)

    if credits <= 0:
        await ctx.send("No tienes suficientes créditos para jugar.")
        return

    category = ctx.guild.get_channel(1140535910795071568)  # Replace with your category ID
    private_channel_name = f'slots-{ctx.author.name}'

    # Check if a channel with the same name already exists
    game_channel = discord.utils.get(category.text_channels, name=private_channel_name)

    if not game_channel:
        # Create a new channel if it doesn't exist
        game_channel = await category.create_text_channel(name=private_channel_name)

        # Grant necessary permissions to the author in the new channel
        member = ctx.author
        await game_channel.set_permissions(member, read_messages=True, send_messages=True, read_message_history=True)

    if bet_amount <= 0:
        await game_channel.send("La apuesta debe ser mayor que 0.")
        return

    for role_name in user_roles:
            if role_name in max_slots_bets:
                if bet_amount < 100:
                    await game_channel.send("La apuesta minima es de $100")
                elif bet_amount > max_slots_bets[role_name]:
                    await game_channel.send(f"Disculpa, {role_name} solo puede apostar hasta {max_slots_bets[role_name]} creditos.")
                elif bet_amount <= max_slots_bets[role_name] and bet_amount >= 100:
                    if bet_amount > credits:
                        await game_channel.send(f"No dispones de esa cantidad")
                    else:
                        results = [[random.choice(slot_icons) for _ in range(num_rows)] for _ in range(num_columns)]

                        slot_display = "\n".join(" ".join(results[col][row] for col in range(num_columns)) for row in range(num_rows))
                        message = await game_channel.send(slot_display)

                        for _ in range(spin_frames):
                            await asyncio.sleep(frame_delay)
                            results = [[random.choice(slot_icons) for _ in range(num_rows)] for _ in range(num_columns)]
                            slot_display = "\n".join(" ".join(results[col][row] for col in range(num_columns)) for row in range(num_rows))
                            await message.edit(content=slot_display)

                        await asyncio.sleep(1)  # Pause before stopping columns one by one

                        for col in range(num_columns):
                            await asyncio.sleep(0.3)  # Pause between stopping columns
                            final_column = [random.choice(slot_icons) for _ in range(num_rows)]
                            results[col] = final_column
                            slot_display = "\n".join(" ".join(results[col][row] for col in range(num_columns)) for row in range(num_rows))
                            await message.edit(content=slot_display)

                        payout_multiplier = await check_win(results)
                        payout = bet_amount * payout_multiplier
                        credits_data = fetchinfo.load_credits()
                        credits += payout
                        credits_data[user_id] = credits
                        fetchinfo.save_credits(credits_data)
                        if payout > 0:
                            await send_formatted_message(slots_channel, f"¡Felicidades!. {ctx.author.display_name} ha ganado {payout} creditos")
                        else: await send_formatted_message(slots_channel, f"{ctx.author.display_name} ha perdido {bet_amount} creditos")
                        await game_channel.send(f"Slots detenido. Apuesta: {bet_amount}. Pago: {payout}.")
                else:
                    await game_channel.send(f"Disculpa, {role_name} solo puede apostar hasta {max_slots_bets[role_name]} creditos.")

@bot.command(name="slots")
@commands.has_any_role(*max_slots_bets.keys())
async def slots(ctx, bet_amount: int):
    await ctx.message.delete()
    await run_slots(ctx, bet_amount)

max_craps_bets = {
    'Regular Player': 5000,
    'Silver Player': 10000,
    'Golden Player': 20000,
    'Diamond Player': 250000,
    'Propietario': 1000000000000000000000000000000000000
}


@bot.command(name="craps")
@commands.has_any_role(*max_craps_bets.keys()) #Roles with higher bet ceiling
async def craps(ctx, bet_amount: int):
    user_roles = [role.name for role in ctx.author.roles]
    user_id = str(ctx.author.id)
    user_id_int = int(user_id)
    credits = fetchinfo.load_credits().get(user_id, 0)
    active_craps_players = []
    # Send a formatted message to the blackjack channel
    craps_channel = ctx.guild.get_channel(1148778056840921139)

    if credits <= 0:
        await ctx.send("No tienes suficientes créditos para jugar.")
        return

    if user_id_int in active_craps_players:
        await ctx.send("Ya estas jugando.")
        return

    active_craps_players.append(user_id)

    category = ctx.guild.get_channel(1140535910795071568)  # Replace with your category ID
    private_channel_name = f'craps-{ctx.author.name}'

    # Check if a channel with the same name already exists
    game_channel = discord.utils.get(category.text_channels, name=private_channel_name)

    if not game_channel:
        # Create a new channel if it doesn't exist
        game_channel = await category.create_text_channel(name=private_channel_name)

        # Grant necessary permissions to the author in the new channel
        member = ctx.author
        await game_channel.set_permissions(member, read_messages=True, send_messages=True, read_message_history=True)

    for role_name in user_roles:
            if role_name in max_craps_bets:
                if bet_amount < 1000:
                    await game_channel.send("La apuesta minima es de $1000")
                elif bet_amount > max_craps_bets[role_name]:
                    await game_channel.send(f"Disculpa, {role_name} solo puede apostar hasta {max_craps_bets[role_name]} creditos.")
                elif bet_amount <= max_craps_bets[role_name] and bet_amount >= 1000:
                    if bet_amount > credits:
                        await game_channel.send(f"No dispones de esa cantidad")
                    else:
                        active_craps_players.append(user_id)
                        await game_channel.send(f"Has apostado {bet_amount} creditos")
                        await asyncio.sleep(1)
                        await game_channel.send("Lanzando dados...")
                        await asyncio.sleep(1)
                        p_dice1 = random.randint(1,6)
                        p_dice2 = random.randint(1,5)
                        await game_channel.send(f"Has sacado un {p_dice1} y un {p_dice2}")
                        p_total = p_dice1 + p_dice2
                        await asyncio.sleep(1)
                        await game_channel.send("El crupier esta lanzando sus dados...")
                        await asyncio.sleep(1)
                        b_dice1 = random.randint(3,6)
                        b_dice2 = random.randint(1,6)
                        await game_channel.send(f"El crupier ha sacado un {b_dice1} y un {b_dice2}")
                        b_total = b_dice1 + b_dice2
                        await asyncio.sleep(1)
                        await game_channel.send(f"Tienes un total de {p_total} y el crupier tiene un total de {b_total}")
                        active_craps_players.remove(user_id)
                        if b_total == 9:
                            await game_channel.send(f"El crupier ha sacado el 9 maldito. Has perdido {bet_amount*2} creditos")
                            await send_formatted_message(craps_channel, f"{ctx.author.display_name} ha perdido {bet_amount*2} creditos contra el 9 maldito")
                            credits_data = fetchinfo.load_credits()
                            if credits >= bet_amount*2:
                                credits -= bet_amount*2
                            else: credits -= bet_amount
                            credits_data[user_id] = credits
                            fetchinfo.save_credits(credits_data)
                        elif p_total > b_total and p_total != 7 and b_total != 9:
                            await game_channel.send(f"Has ganado {bet_amount}")
                            await send_formatted_message(craps_channel, f"¡Felicidades! {ctx.author.display_name} ha ganado {bet_amount} creditos")
                            credits_data = fetchinfo.load_credits()
                            credits += bet_amount
                            credits_data[user_id] = credits
                            fetchinfo.save_credits(credits_data)
                        elif p_total == 7 and b_total != 9:
                            await game_channel.send(f"Has sacado el 7 magico. Has ganado {bet_amount*2}")
                            await send_formatted_message(craps_channel, f"¡Felicidades! {ctx.author.display_name} ha ganado {bet_amount*2} creditos con el 7 magico")
                            credits_data = fetchinfo.load_credits()
                            credits += bet_amount
                            credits_data[user_id] = credits
                            fetchinfo.save_credits(credits_data)
                        elif b_total > p_total and p_total != 7:
                            await game_channel.send(f"El crupier ha sacado mejores dados. Has perdido {bet_amount} creditos")
                            await send_formatted_message(craps_channel, f"{ctx.author.display_name} ha perdido {bet_amount} creditos")
                            credits_data = fetchinfo.load_credits()
                            credits -= bet_amount
                            credits_data[user_id] = credits
                            fetchinfo.save_credits(credits_data)
                        elif b_total == p_total and p_total != 7 and b_total !=9:
                            await game_channel.send(f"Has empatado con el bot")
                            await send_formatted_message(craps_channel, f"{ctx.author.display_name} ha empatado con el bot")
                            credits_data = fetchinfo.load_credits()
                            # credits -= bet_amount
                            credits_data[user_id] = credits
                            fetchinfo.save_credits(credits_data)

                else:
                    await game_channel.send(f"Disculpa, {role_name} solo puede apostar hasta {max_craps_bets[role_name]} creditos.")

max_poker_bets = {
    'Regular Player': 10000,
    'Silver Player': 20000,
    'Golden Player': 50000,
    'Diamond Player': 250000,
    'Propietario': 1000000000000000000000000000000000000
}

active_poker_players = []

card_values = {
            '2': 2, '3': 3, '4': 4, '5': 5, '6': 6,
            '7': 7, '8': 8, '9': 9, '10': 10, 'J': 11,
            'Q': 12, 'K': 13, 'A': 14
        }

@bot.command(name="poker")
@commands.has_any_role(*max_poker_bets.keys()) #Roles with higher bet ceiling
async def poker(ctx):
    global card_values
    user_roles = [role.name for role in ctx.author.roles]
    suits = ['Corazones', 'Diamantes', 'Trebol', 'Picas']
    ranks = ['2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K', 'A']
    user_id = str(ctx.author.id)
    user_id_int = int(user_id)
    credits = fetchinfo.load_credits().get(user_id, 0)
    # Send a formatted message to the blackjack channel
    poker_channel = ctx.guild.get_channel(1148788480114180167)

    if credits <= 0:
        await ctx.send("No tienes suficientes créditos para jugar.")
        return

    if user_id_int in active_poker_players:
        await ctx.send("Ya estas jugando.")
        return

    active_poker_players.append(user_id_int)

    category = ctx.guild.get_channel(1140535910795071568)  # Replace with your category ID
    private_channel_name = f'poker-{ctx.author.name}'

    # Check if a channel with the same name already exists
    game_channel = discord.utils.get(category.text_channels, name=private_channel_name)

    if not game_channel:
        # Create a new channel if it doesn't exist
        game_channel = await category.create_text_channel(name=private_channel_name)

        # Grant necessary permissions to the author in the new channel
        member = ctx.author
        await game_channel.set_permissions(member, read_messages=True, send_messages=True, read_message_history=True)

    async def send_card_message(game_channel, cards):
        image_width = 150  # Adjust the desired width of each card image
        image_height = 220  # Adjust the desired height of each card image

        # Create a list to store card images
        card_images = []

        for card in cards:
            if ' de ' not in card:
                await game_channel.send(f"Invalid card format: {card}")
                return

            rank, suit = card.split(' de ')
            card_image = Image.open(f"cards/{rank.lower()}_of_{suit.lower()}.png")
            card_image = card_image.resize((image_width, image_height))
            card_images.append(card_image)

        # Create a new composite image to combine all card images
        composite_image = Image.new('RGBA', (image_width * len(card_images), image_height))

        # Paste each card image onto the composite image
        for i, card_image in enumerate(card_images):
            composite_image.paste(card_image, (i * image_width, 0))

        # Save the composite image
        composite_image.save('composite_cards.png')

        # Send the composite image as a file in a single message
        await game_channel.send(file=File('composite_cards.png'))

    decks = 1
    all_cards = []
    for _ in range(decks):
        for suit in suits:
            for rank in ranks:
                card = f"{rank} de {suit}"
                all_cards.append(card)

    def calculate_hand_value(hand):
        # Convert card ranks to numerical values for easier comparison

        # Separate the hand into ranks and suits
        ranks = [card.split(' de ')[0] for card in hand]
        suits = [card.split(' de ')[1] for card in hand]

        # Sort the ranks by numerical value
        ranks.sort(key=lambda x: card_values[x])

        # Check for flush (all cards have the same suit)
        is_flush = len(set(suits)) == 1

        # Check for straight (consecutive ranks)
        is_straight = all(card_values[ranks[i]] == card_values[ranks[i - 1]] + 1 for i in range(1, 5))

        # Initialize variables for hand evaluation
        hand_value = 0
        hand_name = ''

        # Check for specific poker hand rankings
        if is_straight and is_flush:
            # Straight flush
            hand_value = 9
            hand_name = 'Escalera Real'
        elif len(set(ranks)) == 2:
            # Four of a kind or Full House
            for rank in set(ranks):
                if ranks.count(rank) == 4:
                    # Four of a kind
                    hand_value = 8
                    hand_name = 'Poker'
                    break
                elif ranks.count(rank) == 3:
                    # Full House
                    hand_value = 7
                    hand_name = 'Full House'
                    break
        elif is_flush:
            # Flush
            hand_value = 6
            hand_name = 'Color'
        elif is_straight:
            # Straight
            hand_value = 5
            hand_name = 'Escalera'
        elif len(set(ranks)) == 3:
            # Three of a kind or Two Pairs
            for rank in set(ranks):
                if ranks.count(rank) == 3:
                    # Three of a kind
                    hand_value = 4
                    hand_name = 'Trio'
                    break
            else:
                # Two Pairs
                hand_value = 3
                hand_name = 'Par Doble'
        elif len(set(ranks)) == 4:
            # One Pair
            hand_value = 2
            hand_name = 'Par'
        else:
            # High Card
            hand_value = 1
            hand_name = 'Carta Alta'

        return hand_value, hand_name

    while credits > 0:
        await game_channel.send(f"Actualmente tiene {credits} creditos. ¿Cuánto deseas apostar?")
        try:
            bet_message = await bot.wait_for('message', timeout=30.0, check=lambda message: message.author == ctx.author)
            bet = bet_message.content.lower()
            if bet == 'salir':
                await game_channel.send("Gracias por jugar en Hubet Casino")
                active_poker_players.remove(user_id_int)
                return
            else:
                bet = int(bet)
        except asyncio.TimeoutError:
            await game_channel.send("Tiempo de espera agotado. Vuelve a intentarlo.")
            active_poker_players.remove(user_id_int)
            return
        except ValueError:
            if user_id_int in active_poker_players:
                continue
            else:
                await game_channel.send("Cantidad inválida. Vuelve a intentarlo con un número entero.")
                continue

        for role_name in user_roles:
                if role_name in max_poker_bets:
                    if bet < 2000:
                        await game_channel.send("La apuesta minima es de $2000")
                    elif bet <= max_poker_bets[role_name] and bet >= 2000:
                        if bet > credits:
                            await game_channel.send(f"No dispones de esa cantidad")
                        else:
                            credits -= bet
                            random.shuffle(all_cards)
                            # Deal initial hands
                            player_hand = [all_cards.pop(), all_cards.pop(), all_cards.pop(), all_cards.pop(), all_cards.pop()]
                            dealer_hand = [all_cards.pop(), all_cards.pop(), all_cards.pop(), all_cards.pop(), all_cards.pop()]

                            player_value = calculate_hand_value(player_hand)
                            dealer_value = calculate_hand_value(dealer_hand)
                            await send_card_message(game_channel, player_hand)
                            await game_channel.send(f"Tu mano: {', '.join(player_hand)}. ¿Deseas apostar más? (Sí/No)")
                            try:
                                bet_more_message = await bot.wait_for('message', timeout=30.0, check=lambda message: message.author == ctx.author)
                                bet_more_input = bet_more_message.content.lower()
                                if bet_more_input == 'si':
                                    while True:
                                        await game_channel.send(f"¿Cuánto deseas apostar adicionalmente?")
                                        try:
                                            additional_bet_message = await bot.wait_for('message', timeout=30.0, check=lambda message: message.author == ctx.author)
                                            additional_bet = int(additional_bet_message.content)
                                            if additional_bet <= 0:
                                                await game_channel.send("La apuesta adicional debe ser mayor que 0.")
                                                continue  # Prompt the player again
                                            if additional_bet > credits:
                                                await game_channel.send("No tienes suficientes créditos para esa apuesta adicional.")
                                                continue  # Prompt the player again
                                            if bet > max_poker_bets[role_name]:
                                                await game_channel.send(f"Solo puedes apostar hasta {max_poker_bets[role_name]} creditos.")
                                                continue
                                            elif bet <= max_poker_bets[role_name] and bet >= 1000:
                                                # Deduct the additional bet from the player's credits
                                                credits -= additional_bet
                                            break  # Valid additional bet, exit the loop
                                        except asyncio.TimeoutError:
                                            await game_channel.send("Tiempo de espera agotado. Vuelve a intentarlo.")
                                            active_poker_players.remove(user_id_int)
                                            return
                                        except ValueError:
                                            await game_channel.send("Cantidad inválida. Vuelve a intentarlo con un número entero.")
                                            continue  # Prompt the player again
                                elif bet_more_input == 'no': additional_bet = 0
                                else:
                                    await game_channel.send("Respuesta inválida. Responde 'Sí' o 'No'.")
                                    
                            except asyncio.TimeoutError:
                                await game_channel.send("Tiempo de espera agotado. Vuelve a intentarlo.")
                                active_poker_players.remove(user_id_int)
                                return
                            # Allow the player to exchange cards (up to 5 cards)
                            while True:
                                await game_channel.send("¿Deseas cambiar alguna carta? Si es así, indícala por su posición (ejemplo: 1 3 5), o escribe 'no'.")
                                exchange_message = await bot.wait_for('message', timeout=30.0, check=lambda message: message.author == ctx.author)
                                exchange_input = exchange_message.content.lower()
                                if exchange_input == 'no':
                                    break  # No card exchanges, exit the loop
                                try:
                                    # Parse the positions of cards to exchange
                                    positions_to_exchange = [int(pos) - 1 for pos in exchange_input.split()]
                                    if len(positions_to_exchange) > 5:
                                        await game_channel.send("No puedes cambiar más de 5 cartas.")
                                        continue  # Prompt the player again
                                    for pos in positions_to_exchange:
                                        if pos < 0 or pos >= 5:
                                            await game_channel.send("Posición de carta inválida.")
                                            continue  # Prompt the player again

                                    # Replace the selected cards with new ones from the deck
                                    for pos in positions_to_exchange:
                                        player_hand[pos] = all_cards.pop()

                                    await game_channel.send(f"Tus cartas después del cambio: {', '.join(player_hand)}")
                                    
                                    await send_card_message(game_channel, player_hand)

                                # Calculate the value of the new hand
                                    player_value = calculate_hand_value(player_hand)
                                    break
                                except ValueError:
                                    await game_channel.send("Entrada inválida para cambiar cartas.")
                                    continue  # Prompt the player again

                            # Allow the bot to exchange cards (up to 5 cards) to try and get a winning combo
                            bot_exchange_count = 0
                            bot_exchange_positions = []
                            while bot_exchange_count < 5:
                                # Decide which cards to exchange based on the bot's strategy (you can customize this logic)
                                # For example, let's say the bot always exchanges the lowest ranked cards
                                lowest_rank = min(player_hand, key=lambda card: card_values[card.split(' de ')[0]])
                                lowest_rank_index = player_hand.index(lowest_rank)
                                
                                bot_exchange_positions.append(lowest_rank_index + 1)  # Add 1 to convert to 1-based indexing
                                bot_exchange_count += 1
                                player_hand[lowest_rank_index] = all_cards.pop()

                            # Display the cards the bot is exchanging
                            await game_channel.send(f"El bot cambió las siguientes cartas: {', '.join([str(pos) for pos in bot_exchange_positions])}")
                            # Determine the winner based on hand values
                            if player_value[0] > dealer_value[0]:
                                winner = "Player"
                            elif player_value[0] < dealer_value[0]:
                                winner = "Dealer"
                            else:
                                active_poker_players.remove(user_id_int)
                                # If the hands have the same value, compare high cards
                                player_high_card = max(card_values[rank.split(' de ')[0]] for rank in player_hand)
                                dealer_high_card = max(card_values[rank.split(' de ')[0]] for rank in dealer_hand)
                                bet += additional_bet
                                if player_high_card > dealer_high_card:
                                    winner = "Player"
                                    await send_formatted_message(poker_channel, f"{ctx.author.display_name} ha ganado {bet} creditos")
                                    credits_data = fetchinfo.load_credits()
                                    credits -= (bet*2)
                                    credits_data[user_id] = credits
                                    fetchinfo.save_credits(credits_data)
                                elif player_high_card < dealer_high_card:
                                    winner = "Dealer"
                                    await send_formatted_message(poker_channel, f"{ctx.author.display_name} ha perdido {bet} creditos")
                                    credits_data = fetchinfo.load_credits()
                                    credits_data[user_id] = credits
                                    fetchinfo.save_credits(credits_data)
                                else:
                                    winner = "Empate"
                                    await send_formatted_message(poker_channel, f"{ctx.author.display_name} ha empatado con el dealer")
                                    credits_data = fetchinfo.load_credits()
                                    credits += bet
                                    credits_data[user_id] = credits
                                    fetchinfo.save_credits(credits_data)
                            if winner == 'Player':
                                await send_formatted_message(poker_channel, f"{ctx.author.display_name} ha ganado {bet} creditos")
                            elif winner == 'Dealer':
                                await send_formatted_message(poker_channel, f"{ctx.author.display_name} ha perdido {bet} creditos")
                            elif winner == "Empate":
                                await send_formatted_message(poker_channel, f"{ctx.author.display_name} ha empatado con el dealer")
                            # Display the hands of both the player and the dealer
                            await game_channel.send(f"Tu mano: {', '.join(player_hand)} ({player_value[1]})")

                            await send_card_message(game_channel, player_hand)
                            await game_channel.send(f"Mano del Dealer: {', '.join(dealer_hand)} ({dealer_value[1]})")

                            await send_card_message(game_channel, dealer_hand)
                            await game_channel.send(f"Ganador: {winner}")
                            return
                    else:
                        await game_channel.send(f"Disculpa, {role_name} solo puede apostar hasta {max_poker_bets[role_name]} creditos.")
                        continue


bot.run(TOKEN)


