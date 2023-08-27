import discord
import asyncio
import fetchinfo
import random
from PIL import Image

from discord.ext import commands
from discord import File


TOKEN = "MTE0MDQ0ODQ2ODQ5MDUyMjYyNA.GY_9HW.JItWljgTVASV9xM2BaFSWkyk"

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


@bot.event
async def on_ready():
    global roulette_game
    print(f'Logged in as {bot.user.name}')
    roulette_game = RouletteGame()
    bot.loop.create_task(roulette_loop())

@bot.event
async def on_member_join(member):
    welcome_channel_id = 1140048546188501032  # Replace with the actual welcome channel ID
    welcome_message = (f"**¡Bienvenido a Casino Deluxe!** {member.mention}.\n"
                      f"Por favor solicita tu rol en el canal <#1140049819914743828> y utiliza tu nombre IC para acceder al servidor.")

    channel = bot.get_channel(welcome_channel_id)
    await channel.send(welcome_message)

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
    blackjack_channel = ctx.guild.get_channel(1145201974304833537)

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


    async def send_card_message(ctx, cards):
        image_width = 150  # Adjust the desired width of each card image
        image_height = 220  # Adjust the desired height of each card image

        composite_image = Image.new('RGBA', (image_width * len(cards), image_height))

        for index, card in enumerate(cards):
            rank, suit = card.split(' de ')
            card_image = Image.open(f"cards/{rank.lower()}_of_{suit.lower()}.png")
            card_image = card_image.resize((image_width, image_height))
            composite_image.paste(card_image, (index * image_width, 0))

        composite_image.save('composite_cards.png')

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
                await game_channel.send("Gracias por jugar en Casino Deluxe")
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

                        for card in player_hand:
                            await send_card_message(ctx, [card])
                        await game_channel.send(f"Tus cartas: {', '.join(player_hand)}. Tienes un total de {player_value}")
                        await send_card_message(ctx, [dealer_hand[0]])
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
                            await send_card_message(ctx, dealer_hand)
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
                                for card in player_hand:
                                    await send_card_message(ctx, [card])
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
                                    for card in player_hand:
                                        await send_card_message(ctx, [card])
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
                                await send_card_message(ctx, dealer_hand)
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
        gif_path = "roulette\gXYMAo.gif"  # Replace with the actual path to your GIF
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
@commands.has_any_role('Regular Player', 'Silver Player', 'Golden Player', 'Diamond Player', 'Propietario')
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
                await game_channel.send("Gracias por jugar en Casino Deluxe")
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

bot.run(TOKEN)


