#!python3.8
import os, sys, glob
import discord
import time, datetime


client = discord.Client()

TOKEN = "" 

voice_text_id = 0
voice_ch_id = 0
admin_role = 70

class Voice():
    def __init__(self, client: discord.Client):
        self.client = client
        self.playlist = self.create_playlist()
    
    async def boot(self):
        self.voice_ch = self.client.get_channel(voice_ch_id)
        self.voice_text_ch = self.client.get_channel(voice_text_id)
        for c in self.client.voice_clients:
            if c.channel.id == voice_ch_id:
                self.vc = c
                print(self.vc.session_id)
                print(self.vc.token)
                break
        else:
            self.vc = None

    def create_playlist(self):
        with open("playlist.txt", "r", encoding="utf-8") as f:
            text = f.read()
        playlist = list()
        for line in text.split("\n"):
            fp = "./music/" + line.strip() + ".mp3"
            playlist.append(fp)
        return playlist

    async def connect(self):
        if self.vc is None:
            print("try connect")
            self.vc = await self.voice_ch.connect()
            print("connected")
            print(self.vc.session_id)
            print(self.vc.token)
            await self.voice_text_ch.send("connected!")
        elif not self.vc.is_connected():
            print("reconnect")
            self.vc = await self.voice_ch.connect()
            print(self.vc.session_id)
            print(self.vc.token)

    def play(self, fp: str):
        #source = discord.FFmpegOpusAudio(source=fp, options='')
        source = discord.FFmpegOpusAudio(source=fp, options='-filter:a "volume=-10dB"')
        self.vc.play(source, after=lambda e: print('done', e))
        print(self.vc.is_playing())
    
    def play_dir(self, path: str):
        files = [os.path.abspath(p) for p in glob.glob(path + "/*")]
        for fp in files:
            print("fp: ", fp)
            self.vc.play(discord.FFmpegOpusAudio(source=fp, options='-filter:a "volume=-10dB"'), after=lambda e: print('done', e))
            while self.vc.is_playing() or self.vc.is_paused():
                time.sleep(1)

    def play_all(self, path: str):
        files = [os.path.abspath(p) for p in glob.glob(path + "/*")]
        last = files.pop(-1)
        print(last)
        befor = "-i " + " -i ".join(files)
        print(befor)
        self.vc.play(discord.FFmpegOpusAudio(source=last, before_options=befor, options='-filter:a "volume=-10dB"'), after=lambda e: print('done', e))

    def play_auto(self, start: bool=False):
        if start:
            for fp in self.playlist:
                print(fp)
            print("play auto start")
        
        fp = self.playlist.pop(0)
        self.playlist.append(fp)
        print("now playing: ", fp)
        source = discord.FFmpegOpusAudio(source=fp, options='-filter:a "volume=-10dB"')
        self.vc.play(source, after=self.play_auto)
        return None

    def pause(self):
        self.vc.pause()
        self.vc.is_paused()
    
    def resume(self):
        self.vc.resume()
    
    def stop(self):
        self.vc.stop()
    
    async def disconnect(self):
        try:
            self.vc.stop()
        except:
            pass
        await self.vc.disconnect()

voice = Voice(client)

@voice.client.event
async def on_ready():
    await voice.boot()
    print("start")

@voice.client.event
async def on_message(message):
    if message.author == voice.client.user:
        return None
    if message.channel.id != voice_text_id:
        return None
    if not admin_role in [r.id for r in message.author.roles]:
        return None
    if message.content.startswith("!connect"):
        print("connect try now")
        await voice.connect()
        print("connected")
    elif message.content.startswith("!playauto"):
        print("play auto")
        voice.play_auto()
    elif message.content.startswith("!play"):
        try:
            fp = "./music/" + " ".join(message.content.split(" ")[1:]).strip() + ".mp3"
            print("fp: ", fp)
            if os.path.isfile(fp):
                print("play: ", fp)
                voice.play(fp)
            elif os.path.isdir(fp):
                print("play dir: ", fp)
                voice.play_all(fp)
            else:
                raise Exception("file is not exist!")
            print("play now")
        except Exception as e:
            print(e)
    elif message.content.startswith("!pause"):
        print("pause")
        voice.pause()
    elif message.content.startswith("!resume"):
        print("resume")
        voice.resume()
    elif message.content.startswith("!stop"):
        print("stop")
        voice.stop()
    elif message.content.startswith("!disconnect"):
        print("disconnect")
        await voice.disconnect()
    else:
        pass

voice.client.run(TOKEN)
