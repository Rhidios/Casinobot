import discord
import asyncio
import datetime
import fetchinfo
import random

from discord.ext import commands
from discord import File

intents = discord.Intents.all()

TOKEN = "MTE0MDQ0ODQ2ODQ5MyNA.GY_9HW.JItWljgTY7Q-PcVqaFSWkyk"

intents = discord.Intents().all()
client = discord.Client(intents = intents)
bot = commands.Bot(command_prefix='/', intents=intents)

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user.name}')

@bot.event
async def on_member_join(member):
    welcome_channel_id = 1140048546188501032  # Replace with the actual welcome channel ID
    welcome_message = (f"**¡Bienvenido a Casino Deluxe!** {member.mention}.\n"
                      f"Por favor solicita tu rol en el canal <#1140049819914743828> y utiliza tu nombre IC para acceder al servidor.")

    channel = bot.get_channel(welcome_channel_id)
    await channel.send(welcome_message)

# Command to check credits
@bot.command(name='wallet')
async def credits(ctx):
    user_id = str(ctx.author.id)
    credits = fetchinfo.load_credits().get(user_id, 0)
    await ctx.send(f"Tienes {credits} creditos.")

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
    for card in cards:
        rank, suit = card.split(' de ')
        card_image = f"cards/{rank.lower()}_of_{suit.lower()}.png"
        await ctx.author.send(file=File(card_image))

async def send_formatted_message(channel, message):
    formatted_message = f"```\n{message}\n```"
    await channel.send(formatted_message)

# Blackjack game logic
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
                return
            else:
                bet = int(bet)
        except asyncio.TimeoutError:
            await ctx.send("Tiempo de espera agotado. Vuelve a intentarlo.")
            return
        except ValueError:
            await ctx.author.send("Cantidad inválida. Vuelve a intentarlo con un número entero.")
            return

        for role_name in user_roles:
            if role_name in max_bets:
                if bet <= max_bets[role_name] and bet > 0:
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

                    # Game logic loop
                    while True:
                        if player_value == 21:
                            break
                        # Ask the player if they want to hit or stand
                        await ctx.author.send("¿Quieres pedir carta (hit) o quedarte (stand)? Responde 'hit' o 'stand'.")
                        try:
                            response = await bot.wait_for('message', timeout=300.0, check=lambda message: message.author == ctx.author and message.content.lower() in ['hit', 'stand'])
                            action = response.content.lower()
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
                            if player_value > 21:
                                await ctx.author.send("Has superado 21. ¡Perdiste!")
                                break

                        elif action == 'stand':
                            # Dealer's turn to draw cards
                            # Calculate dealer's hand value and determine the winner
                            dealer_value = calculate_hand_value(dealer_hand)
                            while dealer_value < 17:
                                new_card = all_cards.pop()
                                dealer_hand.append(new_card)
                                dealer_value = calculate_hand_value(dealer_hand)
                                await asyncio.sleep(1)
                            await send_card_message(ctx, dealer_hand)
                            await ctx.author.send(f"Cartas del dealer: {', '.join(dealer_hand)}. Tiene un total de {dealer_value}")

                        if dealer_value > 21:
                            await ctx.author.send("¡Felicidades, has ganado!")
                            await send_formatted_message(blackjack_channel, f"¡Felicidades!. {ctx.author.display_name} ha ganado {bet * 2} creditos")
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
                        elif dealer_value < player_value:
                            await ctx.author.send("¡Felicidades, has ganado!")
                            await send_formatted_message(blackjack_channel, f"¡Felicidades!. {ctx.author.display_name} ha ganado {bet * 2} creditos")
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
                    return

bot.run(TOKEN)
