import discord
import asyncio
import fetchinfo
import random
from PIL import Image

from discord.ext import commands
from discord import File

intents = discord.Intents.all()

TOKEN = "MTE0MDQ0ODQ2ODQ5MDUyMBZ6687OY7Q-PcVqaFSWkyk"

intents = discord.Intents().all()
client = discord.Client(intents = intents)
bot = commands.Bot(command_prefix='/', intents=intents)
roulette_channel_id = 1140535910795071577  # Replace with the actual roulette channel ID
roulette_channel = None
roulette_channel = bot.get_channel(roulette_channel_id)
bets = []  # Initialize the bets list

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user.name}')
    bot.loop.create_task(roulette_game())

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
        credits = fetchinfo.load_credits().get(user_id, 0)
        await ctx.send(f"Tienes {credits} creditos.")
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
            credits[member_id] += amount
        else:
            credits[member_id] = amount

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
        credits[member_id] -= amount

        fetchinfo.save_credits(credits)

        await ctx.send(f"{amount} creditos han sido retirados de la cuenta de {member.display_name}.")
    else:
        await ctx.send("No se encontró un miembro con ese nombre.")


# Dictionary of allowed max bets for different roles
max_bets = {
    'Regular Player': 25000,
    'Silver Player': 50000,
    'Golden Player': 100000,
    'Diamond Player': 250000,
    'Propietario': 1000000000000000000000000000000000000
}

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

    await ctx.author.send(file=File('composite_cards.png'))

async def send_formatted_message(channel, message):
    formatted_message = f"```\n{message}\n```"
    await channel.send(formatted_message)

active_blackjack_players = {}

# Blackjack
@bot.command(name='blackjack')
@commands.has_any_role(*max_bets.keys()) #Roles with higher bet ceiling
async def blackjack(ctx):
    user_roles = [role.name for role in ctx.author.roles]
    suits = ['Corazones', 'Diamantes', 'Trebol', 'Picas']
    ranks = ['2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K', 'A']
    user_id = str(ctx.author.id)
    credits = fetchinfo.load_credits().get(user_id, 0)
    # Send a formatted message to the blackjack channel
    blackjack_channel = ctx.guild.get_channel(1140535910795071577)

    if credits <= 0:
        await ctx.author.send("No tienes suficientes créditos para jugar.")
        return

    if user_id in active_blackjack_players:
        await ctx.author.send("You are already playing a blackjack game.")
        return

    active_blackjack_players[user_id] = True

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
        await ctx.author.send(f"Actualmente tiene {credits} creditos. ¿Cuánto deseas apostar?")
        try:
            bet_message = await bot.wait_for('message', timeout=300.0, check=lambda message: message.author == ctx.author)
            bet = bet_message.content.lower()
            if bet == 'salir':
                await ctx.author.send("Gracias por jugar en Casino Deluxe")
                del active_blackjack_players[user_id]
                return
            else:
                bet = int(bet)
        except asyncio.TimeoutError:
            await ctx.send("Tiempo de espera agotado. Vuelve a intentarlo.")
            return
        except ValueError:
            if active_blackjack_players[user_id] == True:
                continue
            else:
                await ctx.author.send("Cantidad inválida. Vuelve a intentarlo con un número entero.")
                continue

        for role_name in user_roles:
            if role_name in max_bets:
                if bet <= max_bets[role_name] and bet >= 1000:
                    if bet > credits:
                        await ctx.author.send(f"No dispones de esa cantidad")
                    else:
                        await ctx.author.send(f"Has apostado {bet} creditos")
                        # Shuffle the deck
                        random.shuffle(all_cards)
                        # Deal initial hands
                        player_hand = [all_cards.pop(), all_cards.pop()]
                        dealer_hand = [all_cards.pop(), all_cards.pop()]

                        player_value = calculate_hand_value(player_hand)
                        dealer_value = calculate_hand_value(dealer_hand)
                        for card in player_hand:
                            await send_card_message(ctx, [card])
                        await ctx.author.send(f"Tus cartas: {', '.join(player_hand)}. Tienes un total de {player_value}")
                        await send_card_message(ctx, [dealer_hand[0]])
                        await ctx.author.send(f"Carta visible del dealer: {dealer_hand[0]}. Tiene un total de {dealer_hand[0]}")
                        if player_value == 21:
                            bet *= 2.25
                            await ctx.author.send("¡Felicidades, has sacado un Blackjack!")
                            await send_formatted_message(blackjack_channel, f"¡Felicidades!. {ctx.author.display_name} ha ganado {bet} creditos")
                            credits_data = fetchinfo.load_credits()
                            credits += bet
                            credits_data[user_id] = credits
                            fetchinfo.save_credits(credits_data)

                        # Game logic loop
                        while True:
                            # Ask the player if they want to hit or stand
                            await asyncio.sleep(1)
                            await ctx.author.send("¿Quieres pedir carta (hit), doblar (double) o quedarte (stand)? Responde 'hit', 'double' o 'stand'.")
                            print("Waiting for response...")
                            try:
                                response = await bot.wait_for('message', timeout=300.0, check=lambda message: message.author == ctx.author and message.content.lower() in ['hit', 'double', 'stand'])
                                action = response.content.strip().lower()
                                print("Message received:", response.content.strip().lower())
                            except asyncio.TimeoutError:
                                await ctx.send("Tiempo de espera agotado. Vuelve a intentarlo.")
                                return

                            if action == 'hit':
                                new_card = all_cards.pop()
                                player_hand.append(new_card)
                                await ctx.author.send(f"Nueva carta: {new_card}")
                                # Calculate player's hand value and check if it's over 21
                                player_value = calculate_hand_value(player_hand)
                                for card in player_hand:
                                    await send_card_message(ctx, [card])
                                await ctx.author.send(f"Tus cartas: {', '.join(player_hand)}. Tienes un total de {player_value}")
                                await ctx.author.send(f"Carta visible del dealer: {dealer_hand[0]}. Tiene un total de {dealer_hand[0]}")
                                if player_value > 21:
                                    await ctx.author.send("Has superado 21. ¡Perdiste!")
                                    await send_formatted_message(blackjack_channel, f"¡Que pena!. {ctx.author.display_name} ha perdido {bet} creditos")
                                    credits_data = fetchinfo.load_credits()
                                    credits -= bet
                                    credits_data[user_id] = credits
                                    fetchinfo.save_credits(credits_data)
                                    if credits == 0:
                                        await ctx.author.send("No tiene mas creditos")
                                    break

                            elif action == 'double':
                                if bet * 2 <= credits:
                                    bet *= 2
                                    new_card = all_cards.pop()
                                    player_hand.append(new_card)
                                    await ctx.author.send(f"Nueva carta: {new_card}")
                                    # Calculate player's hand value and check if it's over 21
                                    player_value = calculate_hand_value(player_hand)
                                    for card in player_hand:
                                        await send_card_message(ctx, [card])
                                    await ctx.author.send(f"Tus cartas: {', '.join(player_hand)}. Tienes un total de {player_value}")
                                    if player_value > 21:
                                        await ctx.author.send("Has superado 21. ¡Perdiste!")
                                        await send_formatted_message(blackjack_channel, f"¡Que pena!. {ctx.author.display_name} ha perdido {bet} creditos")
                                        credits_data = fetchinfo.load_credits()
                                        credits -= bet
                                        credits_data[user_id] = credits
                                        fetchinfo.save_credits(credits_data)
                                        if credits == 0:
                                            await ctx.author.send("No tiene mas creditos")
                                        break
                                    if player_value <= 21:
                                        action = 'stand'
                                else:
                                    await ctx.author.send("No tienes suficientes créditos para doblar la apuesta.")

                            if action == 'stand':
                                # Dealer's turn to draw cards
                                # Calculate dealer's hand value and determine the winner
                                dealer_value = calculate_hand_value(dealer_hand)
                                while dealer_value < 17:
                                    new_card = all_cards.pop()
                                    dealer_hand.append(new_card)
                                    dealer_value = calculate_hand_value(dealer_hand)
                                await send_card_message(ctx, dealer_hand)
                                await ctx.author.send(f"Cartas del dealer: {', '.join(dealer_hand)}. Tiene un total de {dealer_value}")

                                if dealer_value > 21:
                                    await ctx.author.send("¡Felicidades, has ganado!")
                                    await send_formatted_message(blackjack_channel, f"¡Felicidades!. {ctx.author.display_name} ha ganado {bet} creditos")
                                    credits_data = fetchinfo.load_credits()
                                    credits += bet
                                    credits_data[user_id] = credits
                                    fetchinfo.save_credits(credits_data)
                                elif dealer_value > player_value:
                                    await ctx.author.send("¡Lo sentimos, has perdido!")
                                    await send_formatted_message(blackjack_channel, f"¡Que pena!. {ctx.author.display_name} ha perdido {bet} creditos")
                                    credits_data = fetchinfo.load_credits()
                                    credits -= bet
                                    credits_data[user_id] = credits
                                    fetchinfo.save_credits(credits_data)
                                    if credits == 0:
                                        await ctx.author.send("No tiene mas creditos")
                                elif dealer_value < player_value:
                                    await ctx.author.send("¡Felicidades, has ganado!")
                                    await send_formatted_message(blackjack_channel, f"¡Felicidades!. {ctx.author.display_name} ha ganado {bet} creditos")
                                    credits_data = fetchinfo.load_credits()
                                    credits += bet
                                    credits_data[user_id] = credits
                                    fetchinfo.save_credits(credits_data)
                                else:
                                    await ctx.author.send("¡Ha sido un empate!")
                                    await send_formatted_message(blackjack_channel, f"{ctx.author.display_name} ha empatado con la casa.")

                                break

                else:
                    await ctx.author.send(f"Disculpa, {role_name} solo puede apostar hasta {max_bets[role_name]} creditos.")
                del active_blackjack_players[user_id]

# Define the bet options and their properties
bet_options = {
    'red': {'max_bet': 5000, 'payout': 35},
    'black': {'max_bet': 5000, 'payout': 35},
    'even': {'max_bet': 5000, 'payout': 2},
    'odd': {'max_bet': 5000, 'payout': 2},
    '1-12': {'max_bet': 5000, 'payout': 2},
    '13-24': {'max_bet': 5000, 'payout': 2},
    '25-36': {'max_bet': 5000, 'payout': 2},
    # Add individual numbers with corresponding colors
    '1': {'max_bet': 1000, 'payout': 35, 'color': 'red'},
    '2': {'max_bet': 1000, 'payout': 35, 'color': 'black'},
    '3': {'max_bet': 1000, 'payout': 35, 'color': 'red'},
    '4': {'max_bet': 1000, 'payout': 35, 'color': 'black'},
    '5': {'max_bet': 1000, 'payout': 35, 'color': 'red'},
    '6': {'max_bet': 1000, 'payout': 35, 'color': 'black'},
    '7': {'max_bet': 1000, 'payout': 35, 'color': 'red'},
    '8': {'max_bet': 1000, 'payout': 35, 'color': 'black'},
    '9': {'max_bet': 1000, 'payout': 35, 'color': 'red'},
    '10': {'max_bet': 1000, 'payout': 35, 'color': 'black'},
    '11': {'max_bet': 1000, 'payout': 35, 'color': 'red'},
    '12': {'max_bet': 1000, 'payout': 35, 'color': 'black'},
    '13': {'max_bet': 1000, 'payout': 35, 'color': 'red'},
    '14': {'max_bet': 1000, 'payout': 35, 'color': 'black'},
    '15': {'max_bet': 1000, 'payout': 35, 'color': 'red'},
    '16': {'max_bet': 1000, 'payout': 35, 'color': 'black'},
    '17': {'max_bet': 1000, 'payout': 35, 'color': 'red'},
    '18': {'max_bet': 1000, 'payout': 35, 'color': 'black'},
    '19': {'max_bet': 1000, 'payout': 35, 'color': 'red'},
    '20': {'max_bet': 1000, 'payout': 35, 'color': 'black'},
    '21': {'max_bet': 1000, 'payout': 35, 'color': 'red'},
    '22': {'max_bet': 1000, 'payout': 35, 'color': 'black'},
    '23': {'max_bet': 1000, 'payout': 35, 'color': 'red'},
    '24': {'max_bet': 1000, 'payout': 35, 'color': 'black'},
    '25': {'max_bet': 1000, 'payout': 35, 'color': 'red'},
    '26': {'max_bet': 1000, 'payout': 35, 'color': 'black'},
    '27': {'max_bet': 1000, 'payout': 35, 'color': 'red'},
    '28': {'max_bet': 1000, 'payout': 35, 'color': 'black'},
    '29': {'max_bet': 1000, 'payout': 35, 'color': 'red'},
    '30': {'max_bet': 1000, 'payout': 35, 'color': 'black'},
    '31': {'max_bet': 1000, 'payout': 35, 'color': 'red'},
    '32': {'max_bet': 1000, 'payout': 35, 'color': 'black'},
    '33': {'max_bet': 1000, 'payout': 35, 'color': 'red'},
    '34': {'max_bet': 1000, 'payout': 35, 'color': 'black'},
    '35': {'max_bet': 1000, 'payout': 35, 'color': 'red'},
    '36': {'max_bet': 1000, 'payout': 35, 'color': 'black'},
}

# Add more specific betting options for dozens
for i in range(1, 4):
    dozen_name = f'{i} docena'  # 1era docena, 2da docena, 3ra docena
    bet_options[dozen_name] = {'max_bet': 5000, 'payout': 2}

async def send_time_remaining(time_remaining):
    if roulette_channel:
        message = await roulette_channel.send(f"Quedan {time_remaining} segundos para que comience la ruleta.")
        return message

async def roulette_game():
    global roulette_channel
    while True:
        bets = []  # Reset user bets at the start of each round
        bet_time = 20  # Reset the countdown timer to its initial value
        timer_messages = []

        # Send initial message before betting starts
        roulette_channel = bot.get_channel(roulette_channel_id)
        gif_path = "roulette\gXYMAo.gif"  # Replace with the actual path to your GIF file
        gif_message = await roulette_channel.send(file=discord.File(gif_path))

        # Allow betting for bet_time seconds
        while bet_time > 0:
            if bet_time % 10 == 0:
                timer_message = await send_time_remaining(bet_time)
                timer_messages.append(timer_message)
            await asyncio.sleep(1)
            bet_time -= 1

        # Close betting and display "Apuestas cerradas" message
        if roulette_channel:
            await roulette_channel.send("Apuestas cerradas, espera a que la bola caiga.")

        # Wait a couple of seconds before announcing the results
        await asyncio.sleep(2)

        # Determine the winner
        winning_bet = random.choice(list(bet_options.keys()))
        for bet in bets:
            if bet['choice'] == winning_bet:
                payout = bet['amount'] * bet_options[winning_bet]['payout']
                credits = fetchinfo.load_credits().get(str(bet['user'].id), 0)
                credits += payout
                fetchinfo.save_credits({str(bet['user'].id): credits})
                result_message = await bet['user'].send(f"Felicidades, has ganado {payout} créditos con tu apuesta en {winning_bet.capitalize()}!")
                await asyncio.sleep(3)  # Wait before deleting the result message
                await result_message.delete()  # Delete the result message

        # Announce the winner and reset bet_time
        if roulette_channel:
            winner_message = await roulette_channel.send(f"La bola ha caído en {winning_bet.capitalize()}!")
            await asyncio.sleep(3)  # Wait before deleting the winner message
            await winner_message.delete()  # Delete the winner message

        # Send a message before resetting the roulette timer
        reset_message = await roulette_channel.send("La siguiente apuesta abre en 5 segundos.")
        await asyncio.sleep(5)

        for timer_message in timer_messages:
            if timer_message:
                await timer_message.delete()

        # Delete the reset message
        if reset_message:
            await reset_message.delete()

def parse_and_place_bets(user_input):
    bets = []
    bet_entries = user_input.split(', ')

    for entry in bet_entries:
        choice, amount = entry.split(', ')
        choice = choice.strip()
        amount = int(amount.strip())
        bets.append({'choice': choice, 'amount': amount})
    return bets

ongoing_roulette_commands = {}  # Dictionary to track ongoing roulette commands

def validate_and_deduct_credits(user, bets):
    user_id = str(user.id)
    credits_data = fetchinfo.load_credits()
    available_credits = credits_data.get(user_id, 0)
    total_bet_amount = 0

    for bet in bets:
        choice = bet['choice']
        amount = bet['amount']

        # Check if the choice is valid
        if choice not in bet_options:
            return False

        # Check if the bet amount is valid
        max_bet = bet_options[choice]['max_bet']
        if amount <= 0 or amount > max_bet:
            return False

        total_bet_amount += amount

    # Check if the user has enough credits to place all bets
    if available_credits < total_bet_amount:
        return False

    # Deduct the total bet amount from the user's credits
    available_credits -= total_bet_amount
    credits_data[user_id] = available_credits
    fetchinfo.save_credits(credits_data)

    return True

@bot.command(name='ruleta')
async def ruleta(ctx):
    user = ctx.author
    await user.send("Bienvenido a la ruleta. Por favor, ingresa tus apuestas en el siguiente formato: `elección, cantidad`. Ejemplo: `rojo, 1000`")
    
    try:
        def check(message):
            return message.author == user and message.content.strip().lower() != 'cancelar'
        
        bets_message = await bot.wait_for('message', timeout=60.0, check=check)
        bets_text = bets_message.content.strip()
        
        bets_input = bets_text.split('; ')
        bets = []
        
        for bet_entry in bets_input:
            bet_info = bet_entry.split(', ')
            if len(bet_info) == 2:
                choice, amount = bet_info
                choice = choice.strip().lower()
                amount = int(amount.strip())
                bets.append({'choice': choice, 'amount': amount})
            else:
                await user.send("Formato de apuesta incorrecto. Por favor, utiliza el formato 'elección, cantidad'.")
                return
        
        if validate_and_deduct_credits(user, bets):
            await user.send("Apuestas realizadas con éxito. ¡Buena suerte en la ruleta!")
            bets.extend(ongoing_roulette_commands.get(user.id, []))  # Add the new bets to the ongoing bets
            ongoing_roulette_commands[user.id] = bets
        else:
            await user.send("Ha ocurrido un error al procesar tus apuestas. Por favor, verifica tus apuestas y tu saldo.")
    
    except asyncio.TimeoutError:
        await user.send("Tiempo de espera agotado. Vuelve a intentarlo.")
bot.run(TOKEN)
