import json
import time
import threading

import ed
import discord
from discord.ext import commands


# login to ED with my account
session = ed.EcoleDirecte(ed.Login("ID", "PASS"))
session.login()

# get the homeworks
homeworks_dictionary = session.fetchHomeworks()

# send a discord message to the right channel

# Define the intents
intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix='/', intents=intents)

message = None

async def main():
    try:
        while 1:
            time.sleep(30)
            await sendMessage()
    except KeyboardInterrupt:
        await bot.close()

async def sendMessage():
    global message
    channel = bot.get_channel(1154391800488923227)

    result = "# <@&1154399248880779364> :"  # ping_devoir role
    for date in homeworks_dictionary:
        result += "\n# " + date + " : \n"
        for subject in homeworks_dictionary[date]:
            result += "## " + subject + " : \n"
            if homeworks_dictionary[date][subject]["controle"]: result += "\n## <@&1155812683808002079>\n"  # ping_eval role
            for line in homeworks_dictionary[date][subject]["text"].split("\n"):
                if line == "":
                    result += "\n"
                    continue
                result += "\n> " + line

    if message == None:
        message = await channel.send(result)
    else:
        await message.edit(content = result)

# commandes:
@bot.event
async def on_ready():
    print(f'Connecté en tant que {bot.user.name}')
    await sendMessage()
    thread = threading.Thread(target=main)
    thread.start()

bot.run("TOKEN")


