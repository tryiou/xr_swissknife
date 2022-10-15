#!/usr/bin/python3
from datetime import datetime, timezone

import discord

import config
from config import discord_token,discord_channel

# print(datetime.now(timezone.utc).strftime("%m/%d/%Y, %H:%M:%S"))
# exit()
# parser = argparse.ArgumentParser()
# parser.add_argument("message", help="message to send")
# args = parser.parse_args()
# message = args.message
message = "arg"
client = discord.Client()


async def my_background_task(msg):
    await client.wait_until_ready()
    channel = client.get_channel(discord_channel)
    # PURGE MESSAGED OLDER THAN x DAYS
    x = 2
    async for elem in channel.history():
        if elem.author == client.user:
            message_age = datetime.now() - elem.created_at
            if message_age.total_seconds() > (60 * 60 * 24) * x:
                if elem.content.startswith('CC ALERT!'):
                    print(elem.content)
                    # await elem.delete()
    # SEND MSG
    title = "CC ALERT! " + str(datetime.now(timezone.utc).strftime("%m/%d/%Y,%H:%M:%S")) + " UTC\n"
    content = str(msg)
    result = title + "```" + content + "```"
    await channel.send(result)

    # CLOSE
    await client.close()


@client.event
async def on_ready():
    print('Logged in as')
    print(client.user.name)
    print(client.user.id)
    print('------')
    await client.change_presence(status=discord.Status.idle)


client.loop.create_task(my_background_task(message))
client.run(discord_token)
