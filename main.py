import discord
import asyncio
import fetchinfo
import random
from PIL import Image

from discord.ext import commands
from discord import File

TOKEN = "MTE0MDQ0ODQ2ODQ5MDUZ6687OY7Q-PcVqaFSWkyk"

intents = discord.Intents().all()
client = discord.Client(intents = intents)
bot = commands.Bot(command_prefix='/', intents=intents)

bet_window_open = True
spin_result = None
spin_result_lock = asyncio.Lock()
spin_complete_event = asyncio.Event()
active_blackjack_players = []

@bot.event
async def on_ready():
    global roulette_game
    print(f'Logged in as {bot.user.name}')
    roulette_game = RouletteGame()



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
        await ctx.author.send(f"Tienes {credits} creditos.")
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
    blackjack_channel = ctx.guild.get_channel(1140535910795071577)

    if credits <= 0:
        await ctx.author.send("No tienes suficientes créditos para jugar.")
        return

    if user_id_int in active_blackjack_players:
        await ctx.author.send("Ya estas jugando.")
        return

    active_blackjack_players.append(user_id_int)

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
            bet_message = await bot.wait_for('message', timeout=30.0, check=lambda message: message.author == ctx.author)
            bet = bet_message.content.lower()
            if bet == 'salir':
                await ctx.author.send("Gracias por jugar en Casino Deluxe")
                active_blackjack_players.remove(user_id_int)
                return
            else:
                bet = int(bet)
        except asyncio.TimeoutError:
            await ctx.send("Tiempo de espera agotado. Vuelve a intentarlo.")
            active_blackjack_players.remove(user_id_int)
            return
        except ValueError:
            if user_id_int in active_blackjack_players:
                continue
            else:
                await ctx.author.send("Cantidad inválida. Vuelve a intentarlo con un número entero.")
                continue

        for role_name in user_roles:
            if role_name in max_bets:
                if bet < 1000:
                    await ctx.author.send("La apuesta minima es de $1000")
                elif bet <= max_bets[role_name] and bet >= 1000:
                    if bet > credits:
                        await ctx.author.send(f"No dispones de esa cantidad")
                    else:
                        await ctx.author.send(f"Has apostado {bet} creditos")
                        bj_possible = False
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
                            # bet *= 2.25
                            await ctx.author.send("¡Felicidades, has sacado un Blackjack!")
                            bj_possible = True
                            # Dealer's turn to draw cards
                            # Calculate dealer's hand value and determine the winner
                            dealer_value = calculate_hand_value(dealer_hand)
                            while dealer_value < 17:
                                new_card = all_cards.pop()
                                dealer_hand.append(new_card)
                                dealer_value = calculate_hand_value(dealer_hand)
                            await send_card_message(ctx, dealer_hand)
                            await ctx.author.send(f"Cartas del dealer: {', '.join(dealer_hand)}. Tiene un total de {dealer_value}")
                            if dealer_value > 21 or dealer_value < 21 and dealer_value >= 17:
                                bet *= 1.25
                                await ctx.author.send(f"¡Felicidades, has ganado {bet}!")
                                await send_formatted_message(blackjack_channel, f"¡Felicidades!. {ctx.author.display_name} ha ganado {bet} creditos")
                                credits_data = fetchinfo.load_credits()
                                credits += bet
                                credits_data[user_id] = credits
                                fetchinfo.save_credits(credits_data)
                                active_blackjack_players.remove(user_id_int)
                            elif dealer_value == 21:
                                await ctx.author.send("¡Ha sido un empate!")
                                await send_formatted_message(blackjack_channel, f"{ctx.author.display_name} ha empatado con la casa.")
                                active_blackjack_players.remove(user_id_int)


                        # Game logic loop
                        while not bj_possible:
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
                                active_blackjack_players.remove(user_id_int)
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
                                        active_blackjack_players.remove(user_id_int)
                                    break
                                if player_hand == 21:
                                    action == 'stand'

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
                                            active_blackjack_players.remove(user_id_int)
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
                                    await ctx.author.send(f"¡Felicidades, has ganado {bet}!")
                                    await send_formatted_message(blackjack_channel, f"¡Felicidades!. {ctx.author.display_name} ha ganado {bet} creditos")
                                    credits_data = fetchinfo.load_credits()
                                    credits += bet
                                    credits_data[user_id] = credits
                                    fetchinfo.save_credits(credits_data)
                                    break
                                elif dealer_value > player_value:
                                    await ctx.author.send("¡Lo sentimos, has perdido!")
                                    await send_formatted_message(blackjack_channel, f"¡Que pena!. {ctx.author.display_name} ha perdido {bet} creditos")
                                    credits_data = fetchinfo.load_credits()
                                    credits -= bet
                                    credits_data[user_id] = credits
                                    fetchinfo.save_credits(credits_data)
                                    if credits == 0:
                                        await ctx.author.send("No tiene mas creditos")
                                        active_blackjack_players.remove(user_id_int)
                                    break
                                elif dealer_value < player_value:
                                    await ctx.author.send(f"¡Felicidades, has ganado {bet}!")
                                    await send_formatted_message(blackjack_channel, f"¡Felicidades!. {ctx.author.display_name} ha ganado {bet} creditos")
                                    credits_data = fetchinfo.load_credits()
                                    credits += bet
                                    credits_data[user_id] = credits
                                    fetchinfo.save_credits(credits_data)
                                    break
                                else:
                                    await ctx.author.send("¡Ha sido un empate!")
                                    await send_formatted_message(blackjack_channel, f"{ctx.author.display_name} ha empatado con la casa.")
                                    break

                else:
                    await ctx.author.send(f"Disculpa, {role_name} solo puede apostar hasta {max_bets[role_name]} creditos.")


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




bot.run(TOKEN)


