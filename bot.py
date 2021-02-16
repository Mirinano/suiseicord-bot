#!python3.8
import sys, os, shutil, copy
import asyncio, threading
import time, datetime
import json, re, requests
import urllib.parse
import urllib.request
from urllib.parse import urlencode
import random
from PIL import Image
from PIL import ImageDraw
from PIL import ImageFilter

import discord #1.3

#original
from __init__ import Developer
import API_token
import log_format 
import fw_wrap
import cmd_trigger
import cmd_msg
import help_msg
import words

class Translation:
    #info
    API_KEY = API_token.translate_API_KEY
    URL = "https://translation.googleapis.com/language/translate/v2"
    
    def translate(self, content:str, target:str) -> tuple:
        detect_sample = content.split("\n")[0] #first line
        source, confidence = self.detect(detect_sample)
        result = self.translation(content, target, source)
        return result, target, source, confidence

    def detect(self, content:str) -> tuple:
        url = Translation.URL + "/detect?key=" + Translation.API_KEY + "&q=" + content
        rr=requests.get(url)
        unit_aa=json.loads(rr.text)
        language = unit_aa["data"]["detections"][0][0]["language"]
        confidence = str(int(unit_aa["data"]["detections"][0][0]["confidence"] * 100))
        return language, confidence

    def translation(self, content:str, target:str, source:str) -> tuple:
        url = Translation.URL + "?key=" + Translation.API_KEY
        content = self.__encode_content(content)
        url += "&q={0}&source={1}&target={2}".format(content, source, target)
        rr=requests.get(url)
        unit_aa = json.loads(rr.text)
        #error check
        try:
            result = unit_aa["data"]["translations"][0]["translatedText"].replace("&#39;", "'").replace("&lt;", "<").replace("&gt;", ">")
        except:
            if unit_aa.get("error") is not None: #API error
                result = "TranslationError: \n\tCode: {0}\n\tMessage: {1}".format(unit_aa["error"]["code"], unit_aa["error"]["message"])
            else:
                result = "TranslationError: Unknown error."
        return result
    
    def __encode_content(self, content):
        return urllib.parse.quote(content, safe='')
    
    def get_translatable_lang(self) -> tuple:
        url = Translation.URL + "/languages?key=" + Translation.API_KEY
        rr=requests.get(url)
        unit_aa=json.loads(rr.text)
        return (d.get("language") for d in unit_aa["data"]["languages"])

    def check_lang(self, lang) -> bool:
        return lang in self.languages
    
    #test method
    def test_translation(self, content:str, target:str, source:str) -> tuple:
        url = Translation.URL + "?key=" + Translation.API_KEY
        content = self.__encode_content(content)
        print(content)
        url += "&q={0}&source={1}&target={2}".format(content, source, target)
        rr=requests.get(url)
        unit_aa=json.loads(rr.text)
        print(unit_aa)

class Minesweeper():
    emoji = ["0️⃣", "1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "💣"]
    def __init__(self):
        pass

    def create_bombs(self, col: int, row: int, bomb: int) -> list:
        l = [0] * row * col
        for r in random.sample(range(row * col), k=bomb):
            l[r] = -1
        return [l[i:i + col] for i in range(0, len(l), col)]

    def count_up(self, l: list):
        col = len(l)
        row = len(l[0])
        for c in range(col):
            for r in range(row):
                if l[c][r] != -1:
                    continue
                for i in range(-1, 2, 1):
                    cc = c + i
                    if -1 < cc < col:
                        if l[cc][r] != -1:
                            l[cc][r] += 1
                        if r-1 > -1 and l[cc][r-1] != -1:
                            l[cc][r-1] += 1
                        if r+1 < row and l[cc][r+1] != -1:
                            l[cc][r+1] += 1
        return l
    
    def str_list(self, l: list):
        col = len(l)
        row = len(l[0])
        result = list()
        for c in range(col):
            result.append(list())
            for r in range(row):
                result[c].append(self.emoji[l[c][r]])
        return result
    
    def create_content(self, l: list):
        col = len(l)
        row = len(l[0])
        s = ""
        for c in range(col):
            s += "||" + "|| ||".join(l[c]) + "||\n"
        return s
    
    def minesweeper(self, bomb: int=10, col: int=10, row: int=10) -> str:
        fild = self.create_bombs(col, row, bomb)
        self.count_up(fild)
        s_list = self.str_list(fild)
        return self.create_content(s_list)

class Talk():
    def __init__(self, config:dict, client:discord.Client):
        self.config = config
        self.client = client

    def load_talk(self):
        pass

class Bot(Translation, Minesweeper):
    def __init__(self, config:dict, client:discord.Client):
        self.config = config
        self.client = client

        #bot info
        self.bot_color = self.change_color_code()
        self.op_role = self.create_op_role()
        self.bot_dir = "./bot/{0}/".format(self.config["NAME"])

        self.guild_ch_type = (discord.TextChannel, discord.VoiceChannel, discord.CategoryChannel)

        #system message directory
        self.sys_msg_dir = self.bot_dir + "messages/"

        #log directory info
        ##tmp dir
        self.tmp = self.bot_dir + "tmp/"
        ##text log
        self.log_dir = self.bot_dir + "log/"
        self.check_path_exits(self.log_dir)
        self.statistics_log = self.log_dir + "{0}/statistics.txt"
        self.statistics = self.log_dir + "statistics.csv"
        self.msg_log = self.log_dir + "{0}/msg_log/{1}.txt"
        self.msg_change_log = self.log_dir + "{0}/msg_change_log/{1}.txt"
        self.msg_delete_log = self.log_dir + "{0}/msg_delete_log/{1}.txt"
        self.msg_zip_log = self.bot_dir + "zip_log/"
        self.check_path_exits(self.msg_zip_log)
        ##voice log
        voice_log_dir = self.bot_dir + "voice_log/"
        voice_log_archive_dir = voice_log_dir + "archive/"
        self.voice_log = voice_log_dir + "{}.txt"
        self.voice_log_archive = voice_log_archive_dir + "{}.txt"
        self.check_path_exits(voice_log_archive_dir)
        self.voice_afk_log()
        ##image dir
        self.image_dir = self.bot_dir + "images/"
        ##load donate
        self.donate_channel = self.config.get("donate_channel")
        self.donate_word = self.config.get("donate_word")
        self.donate_emoji = self.config.get("donate_emoji")
        self.donate_msgs = list()
        self.donate_formlink = self.config.get("donate_formlink")
        self.donate_entrys = self.config.get("donate_entrys")
        self.donate_report_id = self.config.get("donate_report")

        #setup
        self.load_spam()
        self.load_alert()
        self.load_role()

    async def login(self):
        self.create_op_role_mention()
        await self.set_frequent_data()
        await self.load_capture_message()
        self.load_voice_notice()
        await self.client.request_offline_members(self.action_server)
        if self.donate_report_id is not None:
            self.donate_report = self.client.get_channel(self.donate_report_id)

    #test method
    async def launch_report(self):
        ch = self.client.get_channel(self.config["launch_report"])
        content = "{0} has started. \nStartup time: {1}".format(self.client.user.name, datetime.datetime.now().strftime("%Y/%m/%d %H:%M:%S"))
        await ch.send(content)
    
    async def send_test_msg(self):
        ch = self.client.get_channel(self.config["test_ch"])
        content = "this is test msg. \n\ttime:{}".format(datetime.datetime.now().strftime("%Y/%m/%d %H:%M:%S"))
        await ch.send(content)

    #setup method
    async def set_frequent_data(self):
        self.action_server = self.client.get_guild(self.config["action_server_id"])
        self.admin_action_ch = self.client.get_channel(self.config["admin_action_ch_id"])

    async def load_capture_message(self):
        if self.config["reaction_authentication"]:
            self.reaction_authentication_msg = await self.capture_message(self.config["reaction_authentication_msg"])
        if self.config["count_role"]:
            self.count_role_msg = await self.capture_message(self.config["count_role_msg"])
        targets = self.config.get("auto_role_emoji_msg")
        if targets is not None and len(targets) > 0:
            self.role_emoji_msg = list()
            for target in targets:
                self.role_emoji_msg.append(await self.capture_message(target))
        
    async def capture_message(self, url:str) -> discord.Message:
        match = re.search(r"\d+/\d+/\d+", url)
        if match:
            url_list = match.group(0).split("/")
            msg = await self.fetch_message(int(url_list[1]), int(url_list[2]))
            self.client._connection._messages.append(msg)
            return msg
        else:
            return None
    
    def capture_message_id(self, url:str) -> int:
        match = re.search(r"\d+/\d+/\d+", url)
        if match:
            url_list = match.group(0).split("/")
        return url_list

    async def fetch_message(self, ch_id:int, msg_id:int):
        channel = self.client.get_channel(ch_id)
        data = await self.client.http.get_message(channel.id, msg_id)
        return self.client._connection.create_message(channel=channel, data=data)

    def load_voice_notice(self):
        self.voice_notice_join  = self.load_voice_notice2("voice_notice_join")
        self.voice_notice_left  = self.load_voice_notice2("voice_notice_left")
        self.voice_notice_admin = self.client.get_channel(self.config.get("voice_notice_admin")) if self.config.get("voice_notice_admin") is not None else None

    def load_voice_notice2(self, k: str):
        if self.config.get(k) is None:
            return dict()
        data = self.config.get(k)
        for key in data:
            data[key] = self.client.get_channel(data[key])
        return data

    def load_spam(self):
        fp = self.bot_dir + "spam.txt"
        with open(fp, "r", encoding="utf-8") as f:
            content = f.read()
        self.spam_words = set(content.strip().split("\n"))
        with open("spam.txt", "r", encoding="utf-8") as f:
            content = f.read()
        for word in content.strip().split("\n"):
            self.spam_words.add(word)
        self.spam_words.discard("")
        self.update_spam()

    def load_alert(self):
        fp = self.bot_dir + "alert.txt"
        with open(fp, "r", encoding="utf-8") as f:
            content = f.read()
        self.alert_words = set(content.strip().split("\n"))
        self.alert_words.discard("")
        self.update_alert()

    def update_spam(self):
        self.spam_pattern = "|".join(self.spam_words)

    def update_alert(self):
        self.alert_pattern = "|".join(self.alert_words)

    def load_role(self):
        self.color_role = dict()
        self.color_role_set = set()
        fp = self.bot_dir + "role/color_role.txt"
        with open(fp, "r", encoding="utf-8") as f:
            line = f.readline()
            while line:
                try:
                    text = line.strip().split(",")
                    self.color_role[text[0]] = int(text[1])
                    self.color_role_set.add(int(text[1]))
                except:
                    break
                line = f.readline()
        self.normal_role = dict()
        fp = self.bot_dir + "role/normal_role.txt"
        with open(fp, "r", encoding="utf-8") as f:
            line = f.readline()
            while line:
                try:
                    text = line.strip().split(",")
                except:
                    break
                self.normal_role[text[0]] = int(text[1])
                line = f.readline()
        self.emoji_role = dict()
        fp = self.bot_dir + "role/emoji_role.txt"
        with open(fp, "r", encoding="utf-8") as f:
            line = f.readline()
            while line:
                try:
                    text = line.strip().split(",")
                except:
                    break
                self.emoji_role[text[0]] = int(text[1])
                line = f.readline()

    #check method
    def check_bot_user(self, msg:discord.Message) -> bool:
        if msg.author == self.client.user:
            return True
        else:
            return False

    def check_op_user(self, msg:discord.Message) -> bool:
        if not isinstance(msg.author, discord.Member):
            return True
        roles = {r.name for r in msg.author.roles}
        for op in ["op2", "op3", "op4"]:
            if self.op_role[op] in roles:
                return True
        return False

    def check_path_exits(self, fp:str, create:bool=True) -> bool:
        dir_path = os.path.dirname(fp)
        if os.path.exists(dir_path):
            return True
        elif create:
            self.create_dir(dir_path)
        else:
            pass
        return False
    
    def check_file_exits(self, fp:str) -> bool:
        return os.path.exists(fp)
    
    def create_dir(self, fp:str) -> None:
        os.makedirs(fp)
        return None
    
    def check_send_log_day(self) -> str:
        return datetime.datetime.now().strftime("%Y-%m-%d")

    def check_server(self, target) -> bool:
        if self.config["action_server_id"] == 0: #all server
            return True
        if isinstance(target, self.guild_ch_type):
            return target.guild.id == self.config["action_server_id"]
        elif isinstance(target, discord.Guild):
            return target.id == self.config["action_server_id"]
        elif isinstance(target, discord.Message):
            if isinstance(target.channel, self.guild_ch_type):
                return target.channel.guild.id in self.config["action_server_id"]
            else:
                return False
        elif isinstance(target, discord.Member):
            return target.guild.id == self.config["action_server_id"]
        else:
            return False

    def check_cmd_start(self, msg:discord.Message, trigger:tuple) -> bool:
        if msg.content.startswith(trigger[0]):
            if self.config["op"][trigger[1]] in [r.name for r in msg.author.roles]:
                return True
            elif msg.author.guild_permissions.administrator:
                return True
            else:
                return False
        return False

    def check_permission_send_msg(self, ch:discord.abc.GuildChannel, member:discord.Member) -> bool:
        return ch.permissions_for(member).send_messages

    def check_permission_read_message_history(self, ch:discord.abc.GuildChannel, member:discord.Member) -> bool:
        return ch.permissions_for(member).read_message_history
    
    def check_permission_read_message(self, ch:discord.abc.GuildChannel, member:discord.Member) -> bool:
        return ch.permissions_for(member).read_messages

    def create_role_set_name(self, member:discord.Member) -> set:
        return {r.name for r in member.roles}
    
    def create_role_set_id(self, member:discord.Member) -> set:
        return {r.id for r in member.roles}

    def create_op_role(self) -> dict:
        r_dict = dict()
        for k, v in self.config["op"].items():
            r_dict[k] = v
            if r_dict.get(v) is None:
                r_dict[v] = list()
            r_dict[v].append(k)
        return r_dict

    def create_op_role_mention(self) -> dict:
        server = self.client.get_guild(self.config["action_server_id"])
        if server is None:
            print("server is not found")
            return None
        r_dict = dict()
        for role in server.roles:
            if role.name in list(self.config["op"].values()):
                if role.name != "@everyone":
                    for key in self.op_role[role.name]:
                        r_dict[key] = role.mention
                else:
                    r_dict["op1"] = "everyone"
        self.op_role_mention = r_dict

    def create_msg_url(self, msg:discord.Message) -> str:
        return log_format.msg_url.format(
            server = "@me" if isinstance(msg.channel, (discord.DMChannel, discord.GroupChannel)) else msg.guild.id,
            ch = msg.channel.id,
            msg = msg.id
        )

    #help action
    async def help(self, msg:discord.Message):
        content = msg.content.strip(" ")
        if content == "/help":
            op_role_name = {self.config["op"]["op2"], self.config["op"]["op3"], self.config["op"]["op4"]}
            member_role = self.create_role_set_name(msg.author)
            target_role = op_role_name & member_role
            op_level = list()
            for role_name in target_role:
                if self.op_role.get(role_name) is not None:
                    op_level = op_level + self.op_role.get(role_name)
            cmd = help_msg.main_help.format("\n".join(["\n".join(help_msg.help_cmd.get(h)) for h in op_level]))
            
            await msg.channel.send(cmd)
        else:
            target = content.split(" ")[1].strip("/ ")
            cmd = help_msg.help_message.get(target)
            cmd = cmd if cmd is not None else "そのようなコマンドはありません。"
            await msg.channel.send(cmd)

    #save log method
    def save_msg_log(self, msg:discord.Message, * , fp:str=None, write:bool=True):
        ch_name = msg.channel.name if isinstance(msg.channel, self.guild_ch_type) else "DM"
        save_content = log_format.msg_log.format(
            time = msg.created_at.strftime("%Y/%m/%d %H:%M:%S"),
            user = self.save_author(msg.author),
            msg_id = msg.id,
            msg_type = msg.type.name if isinstance(msg.type, discord.MessageType) else "other type",
            attachments = "\n".join([attach.url for attach in msg.attachments]),
            embed = "無" if msg.embeds is None else ("有" if len(msg.embeds) > 0 else "無"),
            content = self.content_fw_wrap(msg.content)
        ) + "\n" + "-"*75 + "\n"
        if write:
            fp = self.msg_log.format(datetime.datetime.now().strftime("%Y-%m-%d"), ch_name) if fp is None else fp
            self.write_file(fp, save_content)
            return None
        else:
            return save_content

    def save_msg_change_log(self, before:discord.Message, after:discord.Message):
        if before.edited_at is None:
            return
        ch_name = after.channel.name if isinstance(after.channel, self.guild_ch_type) else "DM"
        save_content = log_format.msg_change_log.format(
            after_time = after.created_at.strftime("%Y/%m/%d %H:%M:%S"),
            before_time = before.edited_at.strftime("%Y/%m/%d %H:%M:%S"),
            user = self.save_author(after.author),
            msg_id = after.id,
            msg_type = after.type.name if isinstance(after.type, discord.MessageType) else "other type",
            attachments = "\n".join([attach.url for attach in after.attachments]),
            embed = "無" if after.embeds is None else ("有" if len(after.embeds) > 0 else "無"),
            before_content = self.content_fw_wrap(before.content),
            after_content = self.content_fw_wrap(after.content)
        ) + "\n" + "-"*75 + "\n"
        fp = self.msg_change_log.format(datetime.datetime.now().strftime("%Y-%m-%d"), ch_name)
        return self.write_file(fp, save_content)
    
    def save_msg_delete_log(self, msg:discord.Message):
        ch_name = msg.channel.name if isinstance(msg.channel, self.guild_ch_type) else "DM"
        save_content = log_format.msg_delete_log.format(
            delete_time = datetime.datetime.now().strftime("%Y/%m/%d %H:%M:%S"),
            time = msg.created_at.strftime("%Y/%m/%d %H:%M:%S"),
            user = self.save_author(msg.author),
            msg_id = msg.id,
            msg_type = msg.type.name if isinstance(msg.type, discord.MessageType) else "other type",
            attachments = "\n".join([attach.url for attach in msg.attachments]),
            embed = "無" if msg.embeds is None else ("有" if len(msg.embeds) > 0 else "無"),
            content = self.content_fw_wrap(msg.content)
        ) + "\n" + "-"*75 + "\n"
        fp = self.msg_delete_log.format(datetime.datetime.now().strftime("%Y-%m-%d"), ch_name)
        return self.write_file(fp, save_content)
    
    def save_author(self, author):
        if isinstance(author, discord.Member):
            if isinstance(author.nick, str):
                return "{0} (アカウント名: {1}#{2}, ID: {3})".format(author.nick, author.name, author.discriminator, author.id)
        return "{0}#{1} (ID: {2})".format(author.name, author.discriminator, author.id)

    def save_file(self, url:str, fp:str):
        opener = urllib.request.build_opener()
        opener.addheaders=[("User-Agent", "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:47.0) Gecko/20100101 Firefox/47.0")]
        urllib.request.install_opener(opener)
        urllib.request.urlretrieve(url=url, filename=fp) # save file.

    def content_fw_wrap(self, content:str):
        content_list = list()
        for c in content.split("\n"):
            content_list.append("\n".join(fw_wrap.fw_wrap(c, width=70, placeholder="")))
        return "\n".join(content_list)

    def write_file(self, fp:str, content:str, * , dir_create:bool=True, mode="a") -> None:
        self.check_path_exits(fp, create=dir_create)
        with open(fp, mode, encoding="utf-8") as f:
            f.write(content)
        return None

    def create_zip(self, day:str, delete:bool=True) -> str:
        """
        @para day:str %Y-%m-%d

        @return zip file path
        """
        log_dir = self.log_dir + day
        zip_dir = self.msg_zip_log + "-".join(day.split(day)[:1]) #%Y-%m
        zip_file = zip_dir + "/" + day
        self.check_path_exits(zip_dir)
        # create zip file
        shutil.make_archive(zip_file, "zip", root_dir=log_dir)
        zip_file = zip_file + ".zip"
        if delete:
            shutil.rmtree(log_dir)
        return zip_file
    
    def msg_log_dir_list(self, ex_today:bool=True) -> list:
        dirs = list()
        regex = re.compile(r"(\d{4})-(\d{2})-(\d{2})")
        exday = self.check_send_log_day() if ex_today else ""
        for filename in os.listdir(self.log_dir):
            if os.path.isdir(self.log_dir + filename):
                if regex.match(filename) is not None:
                    if filename != exday:
                        dirs.append(filename)
        return dirs

    async def log_request(self, msg:discord.Message):
        if msg.channel.id == self.config["log_request_ch"]:
            if msg.content == self.config["log_request_msg"]:
                await self.send_msg_logs()

    async def send_msg_logs(self):
        for day in self.msg_log_dir_list():
            zip_file = self.create_zip(day)
            file_name = day + ".zip"
            send_msg = "{}のメッセージログです。".format(day)
            ch = self.client.get_channel(self.config["send_logzipfile_channel"])
            file_obj = discord.File(zip_file, filename=file_name)
            await ch.send(content=send_msg, file=file_obj)
    
    async def send_today_msg_log(self):
        day = datetime.datetime.now().strftime("%Y-%m-%d")
        zip_file = self.create_zip(day, delete=False)
        file_name = day + ".zip"
        send_msg = "{}のメッセージログです。".format(day)
        ch = self.client.get_channel(self.config["send_logzipfile_channel"])
        file_obj = discord.File(zip_file, filename=file_name)
        await ch.send(content=send_msg, file=file_obj)

    async def statistics_cmd(self, msg:discord.Message):
        #check cmd type
        c = msg.content.split("\n")[0].split(" ")
        if len(c) > 1:
            cmd = c[1]
        else:
            cmd = None
        # swich
        if cmd == "full":
            await self.full_statistics(msg.guild, msg.channel)
        elif cmd == "simple":
            await self.simple_statistics(msg.guild, msg.channel)
        else:
            await self.save_statistics(msg.guild, send_ch=msg.channel, save=False)

    async def save_statistics(self, server:discord.Guild, day:datetime.datetime=None, * , send_ch:discord.TextChannel=None, save=True) -> str:
        day = datetime.datetime.now() if day is None else day
        if save:
            fp = self.statistics_log.format(day.strftime("%Y-%m-%d"))
        else:
            fp = self.tmp + "statistics.txt"
        top_role = self.search_top_role(server)
        msg_count, write_count, ch_msg_count, users = await self.search_recent_messages_users(server)
        content = log_format.statistics.format(
            server_name = server.name,
            server_id = server.id,
            server_create = server.created_at.strftime("%Y/%m/%d %H:%M:%S"),
            owner = self.save_author(server.owner),
            owner_id = server.owner.id,
            member_count = server.member_count,
            msg_count = msg_count,
            writer_count = write_count,
            region = str(server.region),
            afk_time = str(server.afk_timeout),
            top_role = self.save_role(top_role),
            top_users = self.save_users(self.search_top_role_users(server, top_role), seq="\n\t"),
            default_channel = self.save_channel(server.rules_channel) if server.rules_channel is not None else "None",
            default_role = self.save_role(server.default_role),
            invites = await self.save_invites(server, seq="\n\t", indent=1),
            roles = self.save_roles(server, seq="\n\t"),
            channels = self.save_channels(server, seq="\n\t")
        )
        self.write_file(fp, content, mode="w")
        if send_ch is not None:
            try:
                await send_ch.send(content)
            except discord.HTTPException:
                try:
                    file_obj = discord.File(zip_file, filename="statistscs")
                    await send_ch.send(content="統計情報", file=file_obj)
                except:
                    pass
        return content

    async def simple_statistics(self, server:discord.Guild, send_ch:discord.TextChannel):
        top_role = self.search_top_role(server)
        content = log_format.statistics_simple.format(
            server_name = server.name,
            server_id = server.id,
            server_create = server.created_at.strftime("%Y/%m/%d %H:%M:%S"),
            owner = self.save_author(server.owner),
            owner_id = server.owner.id,
            member_count = str(server.member_count),
            region = str(server.region),
            afk_time = str(server.afk_timeout),
            top_role = self.save_role(top_role),
            top_users = self.save_users(self.search_top_role_users(server, top_role), seq="\n\t"),
            default_channel = self.save_channel(server.rules_channel) if server.rules_channel is not None else "None",
            default_role = self.save_role(server.default_role),
            invites = await self.save_invites_simple(server, seq="\n\t", indent=1),
        )
        await send_ch.send(content)

    async def full_statistics(self, server:discord.Guild, send_ch:discord.TextChannel):
        pass

    def search_top_role(self, server:discord.Guild) -> discord.Role:
        for role in server.roles:
            return role
    
    def search_top_role_users(self, server:discord.Guild, role:discord.Role=None) -> list:
        role = self.search_top_role(server) if role is None else role
        user_list = list()
        for member in server.members:
            if role in member.roles:
                user_list.append(member)
            else:
                continue
        return user_list
    
    async def search_recent_messages_users(self, server:discord.Guild, day:int=1):
        after = datetime.datetime.now() - datetime.timedelta(days=day)
        msg_count = user_count = 0
        users = list()
        users_set = set()
        ch_msg_count = dict()
        for ch in server.text_channels:
            if self.check_permission_read_message(ch, ch.guild.get_member(self.client.user.id)):
                if self.check_permission_read_message_history(ch, ch.guild.get_member(self.client.user.id)):
                    ch_msg_count[str(ch.id)] = 0
                    async for message in ch.history(limit=1000, after=after):
                        ch_msg_count[str(ch.id)] += 1
                        msg_count += 1
                        if not message.author.id in users_set:
                            users_set.add(message.author.id)
                            users.append(message.author)
        return msg_count, len(users_set), ch_msg_count, users

    def save_users(self, users, seq="\n") -> str:
        users = [self.save_author(u) for u in users]
        return seq.join(users)

    def save_users_all(self, server:discord.Guild, seq:str="\n", indent:int=0) -> str:
        pass

    def save_author_mention(self, member) -> str:
        return self.save_author(member) + " (<@{0}>)".format(member.id)

    def save_channel(self, channel, indent=0) -> str:
        if isinstance(channel, self.guild_ch_type):
            return "\t"*indent + "{0} (ID: {1}, pos: {2})".format(channel.name, channel.id, str(channel.position))
        return ""

    def save_channels(self, server:discord.Guild, seq="\n", * , sort:bool=True) -> str:
        channels = [self.save_channel(ch) for ch in server.channels]
        return seq.join(channels)

    def save_role(self, role:discord.Role, indent=0) -> str:
        return "\t"*indent + "{0} (ID: {1}, pos: {2})".format(role.name, role.id, str(role.position))
    
    def save_roles(self, server:discord.Guild, seq="\n", * , sort:bool=True) -> str:
        roles = [self.save_role(r) for r in server.roles]
        return seq.join(roles)
    
    def save_invite(self, invite:discord.Invite, indent=0) -> str:
        return log_format.save_invite.format(
            indent="\t"*indent,
            URL = invite.url,
            created_at = invite.created_at.strftime("%Y/%m/%d %H:%M:%S"),
            uses = str(invite.uses),
            max_uses = "str(invite.max_uses)",
            inviter = self.save_author(invite.inviter),
            channel = self.save_channel(invite.channel)
        )

    async def save_invites_simple(self, server:discord.Guild, seq="\n", indent=0) -> str:
        invites = list()
        for invite in await server.invites():
            invites.append(invite.code)
        return seq.join(invites)

    async def save_invites(self, server:discord.Guild, seq="\n", indent=0) -> str:
        invites = list()
        for invite in await server.invites():
            invites.append(self.save_invite(invite, indent))
        return seq.join(invites)

    #member join/remove action
    async def member_join_log(self, member:discord.Member):
        send_ch = await self.send_welcome_ch(member)
        send_dm = await self.send_welcome_dm(member)
        content = log_format.join_member_message.format(
            time = datetime.datetime.now().strftime("%Y/%m/%d %H:%M:%S"),
            user = self.save_author(member),
            user_id = member.id,
            user_create = member.created_at.strftime("%Y/%m/%d %H:%M:%S"),
            count = str(member.guild.member_count),
            send_ch = send_ch,
            send_dm = send_dm
        )
        ch = self.client.get_channel(self.config["member_join/remove_log_ch"])
        await ch.send(content)
        if self.config["member_count"]:
            await self.member_count(member.guild)
    
    async def send_welcome_ch(self, member:discord.Member, file_name:str="welcome-ch") -> str:
        if self.config["welcome_msg_ch"]:
            if self.config["welcome_msg_ch_random"]:
                pass
            try:
                fp = self.sys_msg_dir + "{}.txt".format(file_name)
                with open(fp, "r", encoding="utf-8") as f:
                    content = f.read()
                content = content.replace("$userid$", str(member.id))
                content = content.replace("$username$", member.name)
                ch = self.client.get_channel(self.config["welcome_msg_ch_id"])
                if self.config.get("welcome_msg_image"):
                    icon_fp = await self.download_icon(member)
                    fp = self.create_image(member.id)
                    send_file = discord.File(fp=fp)
                    await ch.send(content=content, file=send_file)
                    os.remove(fp)
                    os.remove(icon_fp)
                else:
                    await ch.send(content)
                return words.welcome_ch_success
            except:
                return words.welcome_ch_fail
        else:
            return ""
    
    async def send_welcome_dm(self, member:discord.Member, file_name:str="welcome-dm") -> str:
        if self.config["welcome_msg_dm"]:
            if self.config["welcome_msg_dm_random"]:
                pass
            try:
                fp = self.sys_msg_dir + "{}.txt".format(file_name)
                with open(fp, "r", encoding="utf-8") as f:
                    content = f.read()
                await member.send(content)
                return words.welcome_dm_success
            except:
                return words.welcome_dm_fail
        else:
            return ""

    async def member_remove_log(self, member:discord.Member):
        content = log_format.remove_member_message.format(
            time = datetime.datetime.now().strftime("%Y/%m/%d %H:%M:%S"),
            user = self.save_author(member),
            user_id = member.id,
            user_create = member.created_at.strftime("%Y/%m/%d %H:%M:%S"),
            count = str(member.guild.member_count)
        )
        ch = self.client.get_channel(self.config["member_join/remove_log_ch"])
        await ch.send(content)
        if self.config["member_count"]:
            await self.member_count(member.guild)

    async def member_count(self, server:discord.Guild):
        name = log_format.member_count.format(str(server.member_count))
        ch = self.client.get_channel(self.config["member_count_ch"])
        await ch.edit(name=name)

    async def download_icon(self, user):
        avatar_url = user.avatar_url_as(format="png")
        fp = self.tmp + "{}.png".format(user.id)
        await avatar_url.save(fp)
        return fp
    
    def create_image(self, user_id, image:str="welcome"):
        base_path = self.image_dir + "{}.png".format(image)
        base = Image.open(base_path).copy()

        icon_path = self.tmp + "{}.png".format(user_id)
        icon = Image.open(icon_path).copy()
        icon = icon.resize(size=(300, 300), resample=Image.ANTIALIAS)

        mask = Image.new("L", icon.size, 0)
        draw = ImageDraw.Draw(mask)
        draw.ellipse((0, 0, icon.size[0], icon.size[1]), fill=255)
        mask = mask.filter(ImageFilter.GaussianBlur(1))

        icon.putalpha(mask)

        base.paste(icon, (1000, 150), icon)

        circle_path = self.image_dir + "circle.png"
        circle = Image.open(circle_path).copy()

        base.paste(circle, (995, 145), circle)

        fp = self.image_dir + "{0}_{1}.png".format(user_id, image)

        base.save(fp, quality=95)
        return fp

    ##manual cmd
    async def image_cmd(self, msg:discord.Message, op="op3"):
        contents = msg.content.split("\n")
        try:
            image_type = contents[0].split()[1]
            fp = self.image_dir + "{}.png".format(image_type)
            if not self.check_file_exits(fp):
                raise "not iamge"
        except:
            image_type = "welcome"
            fp = self.image_dir + "{}.png".format(image_type)
            if not self.check_file_exits(fp):
                return None
        try:
            user_id = int(self.get_users_id(contents[1])[0])
        except:
            user_id = msg.author.id
        try:
            user = await self.client.fetch_user(user_id)
        except:
            await msg.channel.send(log_format.user_not_found)
            return None
        icon_fp = await self.download_icon(user)
        fp = self.create_image(user.id, image=image_type)
        send_file = discord.File(fp=fp)
        await msg.channel.send(file=send_file)
        os.remove(fp)
        os.remove(icon_fp)

    #reaction authentication system
    async def rule_reaction_add(self, reaction:discord.Reaction, user:discord.Member):
        if reaction.message != self.reaction_authentication_msg:
            return None
        if reaction.emoji == "✅":
            #agreement
            await self.add_role(user, self.config["reaction_authentication_role"])
            await self.send_welcome_ch_auth(user)
            await self.send_welcome_dm_auth(user)
        elif reaction.emoji == "❌":
            #disagreement
            await self.disagreement_rule(user)
            await self.remove_reaction(reaction.message.id, reaction.message.channel.id, reaction.emoji, user.id)
        else:
            #other reactions
            await self.remove_reaction(reaction.message.id, reaction.message.channel.id, reaction.emoji, user.id)

    async def raw_rule_reaction_add(self, payload:discord.RawReactionActionEvent) -> bool:
        if payload.message_id != self.reaction_authentication_msg.id:
            return None
        if str(payload.emoji) == "✅":
            #agreement
            await self.add_role(payload.member, self.config["reaction_authentication_role"])
            await self.send_welcome_ch_auth(payload.member)
            await self.send_welcome_dm_auth(payload.member)
            await self.send_welcome_ch_icebreak(payload.member)
            return True
        elif str(payload.emoji) == "❌":
            #disagreement
            await self.disagreement_rule(payload.member)
            await self.remove_reaction(payload.message_id, payload.channel_id, payload.emoji, payload.user_id)
            return False
        else:
            #other reactions
            await self.remove_reaction(payload.message_id, payload.channel_id, payload.emoji, payload.user_id)
            return False

    #reaction authentication system
    async def rule_reaction_remove(self, reaction:discord.Reaction, user:discord.Member):
        if reaction.message != self.reaction_authentication_msg:
            return None
        if reaction.emoji == "✅":
            await self.remove_role(user, self.config["reaction_authentication_role"])
        return None
    
    async def raw_rule_reaction_remove(self, payload:discord.RawReactionActionEvent):
        if payload.message_id != self.reaction_authentication_msg.id:
            return None
        if str(payload.emoji) == "✅":
            member = self.client.get_guild(payload.guild_id).get_member(payload.user_id)
            if member is not None:
                await self.remove_role(member, self.config["reaction_authentication_role"])
        return None

    async def disagreement_rule(self, member:discord.Member, *, op:str="op2"):
        fp = self.sys_msg_dir + "disagreement_msg.txt"
        with open(fp, "r", encoding="utf-8") as f:
            content = f.read()
        try:
            msg = await member.send(content)
        except:
            log = log_format.disagreement_rule_action_fail.format(
                op = self.op_role_mention[op],
                time = datetime.datetime.now().strftime("%Y/%m/%d %H:%M:%S"),
                target = self.save_author_mention(member),
                log = "DMの送信失敗。"
            )
            await self.client.get_channel(self.config["admin_action_ch_id"]).send(log)
            return None
        try:
            await self.__kick(member.id)
        except:
            await msg.delete()
            log = log_format.disagreement_rule_action_fail.format(
                op = self.op_role_mention[op],
                time = datetime.datetime.now().strftime("%Y/%m/%d %H:%M:%S"),
                target = self.save_author_mention(member),
                log = "DMの送信成功。キックに__失敗__。送信済みDMを削除。"
            )
            await self.client.get_channel(self.config["admin_action_ch_id"]).send(log)
            return None
        return None

    #delete reaction when member left
    async def remove_rule_reaction(self, member:discord.Member):
        try:
            await self.reaction_authentication_msg.remove_reaction("✅", member)
            return True
        except:
            return False

    async def send_welcome_ch_auth(self, member:discord.Member, file_name:str="welcome-ch-auth") -> str:
        if self.config.get("welcome_msg_ch_auth"):
            if self.config.get("welcome_msg_ch_random_auth"):
                pass
            try:
                fp = self.sys_msg_dir + "{}.txt".format(file_name)
                with open(fp, "r", encoding="utf-8") as f:
                    content = f.read()
                content = content.replace("$userid$", str(member.id))
                content = content.replace("$username$", member.name)
                ch = self.client.get_channel(self.config.get("welcome_msg_ch_id_auth"))
                if self.config.get("welcome_msg_image_auth"):
                    icon_fp = await self.download_icon(member)
                    fp = self.create_image(member.id)
                    send_file = discord.File(fp=fp)
                    await ch.send(content=content, file=send_file)
                    os.remove(fp)
                    os.remove(icon_fp)
                else:
                    await ch.send(content)
                return words.welcome_ch_success
            except:
                return words.welcome_ch_fail
        else:
            return ""
    
    async def send_welcome_dm_auth(self, member:discord.Member, file_name:str="welcome-dm-auth") -> str:
        if self.config.get("welcome_msg_dm_auth"):
            if self.config.get("welcome_msg_dm_random_auth"):
                pass
            try:
                fp = self.sys_msg_dir + "{}.txt".format(file_name)
                with open(fp, "r", encoding="utf-8") as f:
                    content = f.read()
                await member.send(content)
                return words.welcome_dm_success
            except:
                return words.welcome_dm_fail
        else:
            return ""

    async def send_welcome_ch_icebreak(self, member:discord.Member, file_name:str="welcome-ch-icebreak") -> str:
        if self.config.get("welcome_msg_ch_icebreak"):
            if self.config.get("welcome_msg_ch_random_icebreak"):
                pass
            try:
                fp = self.sys_msg_dir + "{}.txt".format(file_name)
                with open(fp, "r", encoding="utf-8") as f:
                    content = f.read()
                content = content.replace("$userid$", str(member.id))
                content = content.replace("$username$", member.name)
                ch = self.client.get_channel(self.config.get("welcome_msg_ch_id_icebreak"))
                if self.config.get("welcome_msg_image_icebreak"):
                    icon_fp = await self.download_icon(member)
                    fp = self.create_image(member.id)
                    send_file = discord.File(fp=fp)
                    await ch.send(content=content, file=send_file)
                    os.remove(fp)
                    os.remove(icon_fp)
                else:
                    await ch.send(content)
                return words.welcome_ch_success
            except:
                return words.welcome_ch_fail
        else:
            return ""

    #count role
    async def count_role(self, reaction:discord.Reaction, user:discord.User):
        if reaction.message != self.count_role_msg:
            return None
        if reaction.emoji != "✅":
            return None
        role_count = self.__count_role(reaction.message.guild)
        result = "```\n"
        for role in reaction.message.guild.roles:
            result += "{0} : {1}人\n".format(role.name, str(role_count[role.name]))
        result += "```"
        await self.count_role_msg.edit(content=result)
        await self.remove_reaction(self.count_role_msg.id, self.count_role_msg.channel.id, "✅", user.id)
    
    async def raw_count_role(self, payload:discord.RawReactionActionEvent):
        if payload.message_id != self.count_role_msg.id:
            return None
        if str(payload.emoji) != "✅":
            return None
        server = self.client.get_guild(payload.guild_id)
        role_count = self.__count_role(server)
        result = "```\n"
        for role in server.roles:
            result += "{0} : {1}人\n".format(role.name, str(role_count[role.name]))
        result += "```"
        await self.count_role_msg.edit(content=result)
        await self.remove_reaction(self.count_role_msg.id, self.count_role_msg.channel.id, "✅", payload.user_id)
        
    def __count_role(self, server:discord.Guild=None):
        server = self.client.get_server(self.config["action_server_id"]) if server is None else server
        role_count = dict()
        role_names = [r.name for r in server.roles]
        role_names.reverse()
        for role_name in role_names:
            role_count[role_name] = 0
        for member in server.members:
            for role_name in [r.name for r in member.roles]:
                role_count[role_name] += 1
        return role_count

    async def remove_reaction(self, msg_id, ch_id, emoji, user_id):
        emoji = self._emoji_reaction(emoji)
        await self.client.http.remove_reaction(ch_id, msg_id, emoji, user_id)

    def _emoji_reaction(self, emoji):
        if isinstance(emoji, discord.Reaction):
            emoji = emoji.emoji

        if isinstance(emoji, discord.Emoji):
            return '%s:%s' % (emoji.name, emoji.id)
        if isinstance(emoji, discord.PartialEmoji):
            return emoji._as_reaction()
        if isinstance(emoji, str):
            # Reactions can be in :name:id format, but not <:name:id>.
            # No existing emojis have <> in them, so this should be okay.
            return emoji.strip('<>')

    #voice log
    async def save_voice_log(self, member:discord.Member, before:discord.VoiceState, after:discord.VoiceState):
        action = self.voice_action(before, after)
        if action is None:
            self.voice_user_update(before, after, member)
        elif action == "join":
            if self.voice_start_check(after):
                await self.voice_start_action(after, member)
            self.voice_join_action(after, member)
            await self.voice_join_notice(after, member)
            await self.voice_join_notice_admin(after, member)
        elif action == "remove":
            self.voice_remove_action(before, member)
            await self.voice_left_notice(before, member)
            await self.voice_left_notice_admin(before, member)
            if self.voice_finish_check(before):
                await self.voice_finish_action(before)
        elif action == "move":
            await self.voice_move_action(before, after, member)
        else:
            pass
    
    def voice_action(self, before:discord.VoiceState, after:discord.VoiceState) -> str:
        if ((before.channel is None) or before.afk) and (after.channel is not None): #user join voice channel
            return "join"
        elif (before.channel is not None) and ((after.channel is None) or after.afk): #user remove voice channel
            return "remove"
        elif before.channel != after.channel: #user move voice chanel
            return "move"
        else: #status update
            return None
    
    def save_voice_channel(self, ch:discord.VoiceChannel) -> str:
        if isinstance(ch, discord.VoiceChannel):
            return "{0} (ID: {1})".format(ch.name, ch.id)
        return ""

    def count_voice_members(self, ch:discord.VoiceChannel) -> int:
        return len(ch.members)

    def voice_join_action(self, after:discord.VoiceState, member:discord.Member):
        fp = self.voice_log.format(after.channel.id)
        status = log_format.voice_status.format(
            self_mic = "無効" if after.self_mute else "有効",
            self_speaker = "無効" if after.self_deaf else "有効",
            mic = "無効" if after.mute else "有効",
            speaker = "無効" if after.deaf else "有効"
        )
        content = log_format.voice_join.format(
            time = datetime.datetime.now().strftime("%Y:%m:%dT%H:%M:%S"),
            count = str(self.count_voice_members(after.channel)),
            user = self.save_author(member),
            status = status
        )
        self.write_file(fp, content)
    
    def voice_remove_action(self, before:discord.VoiceState, member:discord.Member):
        fp = self.voice_log.format(before.channel.id)
        status = log_format.voice_status.format(
            self_mic = "無効" if before.self_mute else "有効",
            self_speaker = "無効" if before.self_deaf else "有効",
            mic = "無効" if before.mute else "有効",
            speaker = "無効" if before.deaf else "有効"
        )
        content = log_format.voice_remove.format(
            time = datetime.datetime.now().strftime("%Y:%m:%dT%H:%M:%S"),
            count = str(self.count_voice_members(before.channel)),
            user = self.save_author(member),
            status = status
        )
        self.write_file(fp, content)

    def voice_user_update(self, before:discord.VoiceState, after:discord.VoiceState, member:discord.Member):
        fp = self.voice_log.format(after.channel.id)
        if after.deaf != before.deaf:
            status = log_format.voice_change_status_server.format(
                status = "サーバースピーカー",
                action = "無効" if after.deaf else "有効"
            )
        elif after.mute != before.mute:
            status = log_format.voice_change_status_server.format(
                status = "サーバーマイク",
                action = "無効" if after.mute else "有効"
            )
        elif after.self_deaf != before.self_deaf:
            status = log_format.voice_change_status_self.format(
                status = "スピーカー",
                action = "無効" if after.self_deaf else "有効"
            )
        elif after.self_mute != before.self_mute:
            status = log_format.voice_change_status_self.format(
                status = "マイク",
                action = "無効" if after.self_mute else "有効"
            )
        else:
            return None
        content = log_format.voice_change.format(
            time = datetime.datetime.now().strftime("%Y:%m:%dT%H:%M:%S"),
            count = str(self.count_voice_members(after.channel)),
            user = self.save_author(member),
            content = status
        )
        self.write_file(fp, content)
    
    def voice_start_check(self, after:discord.VoiceState) -> bool:
        return not os.path.exists(self.voice_log.format(after.channel.id))
    
    def voice_finish_check(self, before:discord.VoiceState) -> bool:
        return len(before.channel.members) == 0
    
    async def voice_start_action(self, after:discord.VoiceState, member:discord.Member):
        start_time = datetime.datetime.now().strftime("%Y:%m:%dT%H:%M:%S")
        fp = self.voice_log.format(after.channel.id)
        content = log_format.voice_start.format(
            time = start_time,
            name = after.channel.name,
            id = after.channel.id
        )
        self.write_file(fp, content)
        content = log_format.voice_start_message.format(
            time = start_time,
            user = self.save_author(member),
            user_id = member.id,
            ch_name = after.channel.name,
            ch_id = after.channel.id
        )
        ch = self.client.get_channel(self.config["send_voice_log_ch"])
        await ch.send(content)
    
    async def voice_finish_action(self, before:discord.VoiceState):
        # pass AFK channel
        if before.channel.id == self.config["AFK_channel"]:
            return None
        
        finish_time = datetime.datetime.now()
        fp = self.voice_log.format(before.channel.id)
        log_file = open(fp, "r", encoding="utf-8")
        log_line = log_file.readline()
        r = re.search(r"\d{4}:\d{2}:\d{2}T\d{2}:\d{2}:\d{2}", log_line)
        start_time = datetime.datetime.strptime(r.group(), "%Y:%m:%dT%H:%M:%S")
        operating_time = finish_time - start_time
        h = str(int(operating_time.seconds / 3600))
        m = str(int((operating_time.seconds % 3600) / 60))
        s = str(int(operating_time.seconds % 60))
        operating_time = "{0}日と{1}時間{2}分{3}秒".format(str(operating_time.days), h, m, s)
        finish_time = finish_time.strftime("%Y:%m:%dT%H:%M:%S")
        finish_content = log_format.voice_finish.format(
            time = finish_time,
            operating_time = operating_time
        )
        new_fp = self.voice_log_archive.format(start_time.strftime("%Y-%m-%dT%H-%M-%S"))
        with open(new_fp, "a", encoding="utf-8") as f:
            f.write(log_line)
            log_line = log_file.readline()
            f.write(finish_content)
            while(log_line):
                f.write(log_line)
                log_line = log_file.readline()
        log_file.close()
        os.remove(fp)
        content = log_format.voice_finish_message.format(
            ch_name = before.channel.name,
            ch_id = before.channel.id,
            time = finish_time,
            operating_time = operating_time
        )
        ch = self.client.get_channel(self.config["send_voice_log_ch"])
        send_file = discord.File(fp=new_fp)
        await ch.send(content=content, file=send_file)

    async def voice_move_action(self, before:discord.VoiceState, after:discord.VoiceState, member:discord.Member):
        fp = self.voice_log.format(before.channel.id)
        status = log_format.voice_status.format(
            self_mic = "無効" if before.self_mute else "有効",
            self_speaker = "無効" if before.self_deaf else "有効",
            mic = "無効" if before.mute else "有効",
            speaker = "無効" if before.deaf else "有効"
        )
        content = log_format.voice_remove.format(
            time = datetime.datetime.now().strftime("%Y:%m:%dT%H:%M:%S"),
            count = str(self.count_voice_members(before.channel)),
            user = self.save_author(member),
            user_id = member.id,
            status = log_format.voice_move_before.format(
                ch = self.save_voice_channel(before.channel),
                status = status
            )
        )
        self.write_file(fp, content)
        await self.voice_left_notice(before, member)
        await self.voice_left_notice_admin(before, member)
        if self.voice_finish_check(before):
            await self.voice_finish_action(before)
        if self.voice_start_check(after):
            await self.voice_start_action(after, member)
        fp = self.voice_log.format(after.channel.id)
        status = log_format.voice_status.format(
            self_mic = "無効" if after.self_mute else "有効",
            self_speaker = "無効" if after.self_deaf else "有効",
            mic = "無効" if after.mute else "有効",
            speaker = "無効" if after.deaf else "有効"
        )
        content = log_format.voice_join.format(
            time = datetime.datetime.now().strftime("%Y:%m:%dT%H:%M:%S"),
            count = str(self.count_voice_members(after.channel)),
            user = self.save_author(member),
            user_id = member.id,
            status = log_format.voice_move_after.format(
                ch = self.save_voice_channel(after.channel),
                status = status
            )
        )
        self.write_file(fp, content)
        await self.voice_join_notice(after, member)
        await self.voice_join_notice_admin(after, member)

    def voice_afk_log(self):
        fp = self.voice_log.format(self.config["AFK_channel"])
        if not self.check_file_exits(fp):
            content = "AFKチャンネルのログです。\n\n"
            self.write_file(fp, content)
        else:
            return None

    async def voice_join_notice(self, vs:discord.VoiceState, member:discord.Member):
        ch = self.voice_notice_join.get(str(vs.channel.id))
        if ch is None:
            return
        await ch.send(
            log_format.voice_join_notice.format(
                user = self.user_name(member),
                ch   = vs.channel.name,
            )
        )

    async def voice_left_notice(self, vs:discord.VoiceState, member:discord.Member):
        ch = self.voice_notice_left.get(str(vs.channel.id))
        if ch is None:
            return
        await ch.send(
            log_format.voice_left_notice.format(
                user = self.user_name(member),
                ch   = vs.channel.name,
            )
        )
    
    async def voice_join_notice_admin(self, vs:discord.VoiceState, member:discord.Member):
        if self.voice_notice_admin is None:
            return
        await self.voice_notice_admin.send(
            log_format.voice_join_notice.format(
                user = self.user_name(member),
                ch   = vs.channel.name,
            )
        )

    async def voice_left_notice_admin(self, vs:discord.VoiceState, member:discord.Member):
        if self.voice_notice_admin is None:
            return
        await self.voice_notice_admin.send(
            log_format.voice_left_notice.format(
                user = self.user_name(member),
                ch   = vs.channel.name,
            )
        )

    #admin assist
    ## ban/unban/kick
    async def ban(self, msg:discord.Message, * , op:str="op2"):
        start_time = datetime.datetime.now().strftime("%Y/%m/%d %H:%M:%S")
        content = msg.content.lstrip(cmd_trigger.ban[0]) #remove trigger ward
        cmd = self.spilit_function(content, 2)
        users_id = self.get_users_id(cmd["rest_first"])
        del_day = self.config["ban_del_msg"] if cmd.get("day") is None else (int(cmd.get("day")) if 0 <= int(cmd.get("day")) < 8 else 0)
        dm = True if cmd.get("dm") == "true" else (False if cmd.get("dm") == "false" else self.config["ban_dm"])
        if dm:
            if cmd.get("dm-original") == "true":
                content = cmd.get("rest_last")
            else:
                fp = self.sys_msg_dir + "ban_msg.txt"
                with open(fp, "r", encoding="utf-8") as f:
                    content = f.read()
        else:
            content = None

        # check
        users_info = dict()
        for user_id in users_id:
            try:
                users_info[str(user_id)] = await self.client.fetch_user(user_id)
            except:
                users_id.remove(user_id)
        accept_count = cancel_count = 1
        check_content = log_format.ban_kick_check.format(
            action = "ban",
            cmder = self.save_author(msg.author),
            targets = "\n\t".join([self.save_author(user) for user in users_info.values()]),
            send_dm = str(dm),
            dm_content = content if dm else "送信無し",
            op_level = self.op_role_mention[op],
            accept_count = str(accept_count),
            cancel_count = str(cancel_count)
        )
        check = await self.check_execute_cmd(msg, accept_count, cancel_count, content=check_content, role=self.config["op"][op])
        if check:
            # accept
            await msg.channel.send(log_format.cmd_accept)
        else:
            # cancel
            await msg.channel.send(log_format.cmd_cancel)
            return None
        
        result_list = list()
        for user_id in users_id:
            result = dict()
            try:
                result["user_info"] = users_info[str(user_id)]
                try:
                    if content is None:
                        raise "Content is None"
                    await self.send_dm_message(user_id, content)
                    result["dm"] = True
                except:
                    result["dm"] = False
                try:
                    await self.__ban(user_id)
                    result["ban"] = True
                except:
                    result["ban"] = False
            except discord.NotFound:
                result["user_info"] = "User ID:{} is not found.".format(user_id)
            except:
                result["user_info"] = "unexpected error."
            finally:
                result_list.append(self.result_text(result, "ban"))
        end_time = datetime.datetime.now().strftime("%Y/%m/%d %H:%M:%S")
        content = log_format.ban_kick_result_log.format(
            action = "ban",
            start_time = start_time,
            end_time = end_time,
            details = "\n".join(result_list)
        )
        ch = self.client.get_channel(self.config["admin_action_ch_id"])
        await msg.channel.send(log_format.ban_result)
        await ch.send(content)
    
    async def unban(self, msg:discord.Message):
        start_time = datetime.datetime.now().strftime("%Y/%m/%d %H:%M:%S")
        content = msg.content.lstrip(cmd_trigger.unban[0]) #remove trigger ward
        users_id = self.get_users_id(content)
        result_list = list()
        for user_id in users_id:
            result = dict()
            try:
                result["user_info"] = await self.fetch_user(user_id)
                try:
                    await self.__unban(user_id)
                    result["unban"] = True
                except:
                    result["unban"] = False
            except discord.NotFound:
                result["user_info"] = "User ID:{} is not found.".format(user_id)
            except:
                result["user_info"] = "unexpected error."
            finally:
                result["dm"] = False #not send dm all action
                result_list.append(self.result_text(result, "unban"))
        end_time = datetime.datetime.now().strftime("%Y/%m/%d %H:%M:%S")
        content = log_format.ban_kick_result_log.format(
            action = "unban",
            start_time = start_time,
            end_time = end_time,
            details = "\n".join(result_list)
        )
        ch = self.client.get_channel(self.config["admin_action_ch_id"])
        await msg.channel.send(log_format.unban_result)
        await ch.send(content)

    async def kick(self, msg:discord.Message, * , op:str="op2"):
        start_time = datetime.datetime.now().strftime("%Y/%m/%d %H:%M:%S")
        content = msg.content.lstrip(cmd_trigger.kick[0]) #remove trigger ward
        cmd = self.spilit_function(content, 2)
        users_id = self.get_users_id(cmd["rest_first"])
        dm = True if cmd.get("dm") == "true" else (False if cmd.get("dm") == "false" else self.config["kick_dm"])
        if dm:
            if cmd.get("dm-original") == "true":
                content = cmd.get("rest_last")
            else:
                fp = self.sys_msg_dir + "kick_msg.txt"
                with open(fp, "r", encoding="utf-8") as f:
                    content = f.read()
        else:
            content = None

        # check
        users_info = dict()
        for user_id in users_id:
            try:
                users_info[str(user_id)] = await self.client.fetch_user(user_id)
            except:
                users_id.remove(user_id)
        accept_count = cancel_count = 1
        check_content = log_format.ban_kick_check.format(
            action = "kick",
            cmder = self.save_author(msg.author),
            targets = "\n\t".join([self.save_author(user) for user in users_info.values()]),
            send_dm = str(dm),
            dm_content = content if dm else "送信無し",
            op_level = self.op_role_mention[op],
            accept_count = str(accept_count),
            cancel_count = str(cancel_count)
        )
        check = await self.check_execute_cmd(msg, accept_count, cancel_count, content=check_content, role=self.config["op"][op])
        if check:
            # accept
            await msg.channel.send(log_format.cmd_accept)
        else:
            # cancel
            await msg.channel.send(log_format.cmd_cancel)
            return None

        result_list = list()
        for user_id in users_id:
            result = dict()
            try:
                result["user_info"] = users_info[str(user_id)]
                try:
                    if content is None:
                        raise "Content is None"
                    await self.send_dm_message(user_id, content)
                    result["dm"] = True
                except:
                    result["dm"] = False
                try:
                    await self.__kick(user_id)
                    result["kick"] = True
                except:
                    result["kick"] = False
            except discord.NotFound:
                result["user_info"] = "User ID:{} is not found.".format(user_id)
            except:
                result["user_info"] = "unexpected error."
            finally:
                result_list.append(self.result_text(result, "kick"))
        end_time = datetime.datetime.now().strftime("%Y/%m/%d %H:%M:%S")
        content = log_format.ban_kick_result_log.format(
            action = "kick",
            start_time = start_time,
            end_time = end_time,
            details = "\n".join(result_list)
        )
        ch = self.client.get_channel(self.config["admin_action_ch_id"])
        await msg.channel.send(log_format.kick_result)
        await ch.send(content)

    def result_text(self, result:dict, action:str) -> str:
        if isinstance(result["user_info"], discord.User):
            return log_format.user_info.format(
                user = self.save_author(result["user_info"]),
                user_id = result["user_info"].id,
                user_create = result["user_info"].created_at.strftime("%Y/%m/%d %H:%M:%S"),
                dm = "success" if result["dm"] else "fail",
                action = action,
                judg = "success" if result[action] else "fail"
            )
        else:
            return result["user_info"]
        
    async def __ban(self, user_id:int,  delete_message_days=1, server_id:int=None):
        server_id = server_id if server_id is not None else self.config["action_server_id"]
        await self.client.http.ban(user_id, server_id, delete_message_days)

    async def __unban(self, user_id:int, server_id:int=None):
        server_id = server_id if server_id is not None else self.config["action_server_id"]
        await self.client.http.unban(user_id, server_id)
    
    async def __kick(self, user_id:int, server_id:int=None):
        server_id = server_id if server_id is not None else self.config["action_server_id"]
        await self.client.http.kick(user_id, server_id)

    def get_users_id(self, data:str) -> list:
        match = re.findall(r"\d+", data)
        return [int(x) for x in match]
    
    async def get_users_info(self, ids:list):
        users_list = list()
        for id in ids:
            users_list.append(await self.client.fetch_info(id))
        return users_list
    
    async def send_dm_message(self, user_id:int, content=None):
        ch = await self.get_user_private_channel_by_id(user_id)
        return await ch.send(content)

    async def get_user_private_channel_by_id(self, user_id:int) -> discord.DMChannel:
        found = self.dm_channel(user_id)
        if found is not None:
            return found

        data = await self.client.http.start_private_message(user_id)
        return self.client._connection.add_dm_channel(data)

    def dm_channel(self, user_id:int):
        return self.client._connection._get_private_channel_by_user(user_id)

    async def mass_ban(self, msg:discord.Message, *, op:str="op4"):
        start_time = datetime.datetime.now().strftime("%Y/%m/%d %H:%M:%S")
        users = msg.content.split("\n")[1:]
        
        accept_count = cancel_count = 1
        check_content = log_format.mass_ban_check.format(
            cmder = self.save_author(msg.author),
            targets = "\n".join(users),
            op_level = self.op_role_mention[op],
            accept_count = str(accept_count),
            cancel_count = str(cancel_count)
        )
        check = await self.check_execute_cmd(msg, accept_count, cancel_count, content=check_content, role=self.config["op"][op])
        if check:
            # accept
            await msg.channel.send(log_format.cmd_accept)
        else:
            # cancel
            await msg.channel.send(log_format.cmd_cancel)
            return None
        
        success = list()
        fail = list()
        for user_id in users:
            try:
                await self.__ban(user_id)
                success.append(user_id)
            except Exception as e:
                print(e)
                fail.append(user_id)
        
        end_time = datetime.datetime.now().strftime("%Y/%m/%d %H:%M:%S")
        content = log_format.mass_ban_result.format(
            start_time = start_time,
            end_time = end_time,
            success = "\n".join(success) if success else "None",
            fail = "\n".join(fail) if fail else "None"
        )
        ch = self.client.get_channel(self.config["admin_action_ch_id"])
        await msg.channel.send(log_format.ban_result)
        await ch.send(content)

    ## spam/alert
    async def spam_alert(self, msg:discord.Message):
        if not self.check_bot_user(msg):
            if not self.check_op_user(msg):
                await self.alert(msg)
                await self.spam(msg)

    async def spam(self, msg:discord.Message):
        if not bool(self.spam_pattern):
            return None
        match = re.search(self.spam_pattern, msg.content)
        if not match:
            return None
        try:
            await self.__ban(user_id=msg.author.id)
            report = {"level": words.report, "detail": words.dealing_with_spam, "action": words.ban_succsess}
        except:
            #fail
            report = {"level": words.emergency, "detail": words.spam_occurrence, "action": words.ban_fail}
        finally:
            report["time"] = datetime.datetime.now().strftime("%Y/%m/%d %H:%M:%S")
            report["reason"] = log_format.alert_reasen_match.format(match.group(0))
            report["mentions"] = self.op_role_mention["op2"]
            await self.alert_report(msg, **report)

    async def alert(self, msg:discord.Message):
        if not bool(self.alert_pattern):
            return None
        match = re.search(self.alert_pattern, msg.content)
        if not match:
            return None
        report = {
            "level"   : words.warning,
            "detail"  : words.attention_message,
            "action"  : words.no_action,
            "time"    : datetime.datetime.now().strftime("%Y/%m/%d %H:%M:%S"),
            "reason"  : log_format.alert_reasen_match.format(match.group(0)),
            "mentions": self.op_role_mention["op2"]
        }
        await self.alert_report(msg, **report)
    
    async def alert_report(self, msg:discord.Message, **kwargs):
        content = log_format.alert.format(
            channel = self.save_channel(msg.channel),
            author  = self.save_author_mention(msg.author),
            url = self.create_msg_url(msg),
            content = msg.content, 
            **kwargs
        )
        await self.admin_action_ch.send(content)

    async def spam_cmd(self, msg:discord.Message, _type="local", *, op:str="op3"):
        try:
            action = msg.content.split("\n")[0].split()[1].strip().lower()
            targets = set(msg.content.split("\n")[1:])
            kwargs = {"cat": _type, action: targets}
            print(kwargs)
            self.__edit_spam(**kwargs)
        except:
            pass
        finally:
            await msg.channel.send(self.show_spam())
    
    async def alert_cmd(self, msg:discord.Message, *, op:str="op3"):
        try:
            action = msg.content.split("\n")[0].split()[1].strip().lower()
            targets = set(msg.content.split("\n")[1:])
            kwargs = {action: targets}
            self.__edit_alert(**kwargs)
        except:
            pass
        finally:
            await msg.channel.send(self.show_alert())

    def show_spam(self):
        fp = self.bot_dir + "spam.txt"
        with open(fp, "r", encoding="utf-8") as f:
            local = f.read().strip()
        with open("spam.txt", "r", encoding="utf-8") as f:
            _global = f.read().strip()
        return log_format.show_spam.format(local = local, globals=_global)

    def show_alert(self):
        fp = self.bot_dir + "alert.txt"
        with open(fp, "r", encoding="utf-8") as f:
            local = f.read().strip()
        return log_format.show_alert.format(local = local)

    def __edit_spam(self, add:set=set(), remove:set=set(), cat:str="local", **kwargs):
        for a in add:
            self.spam_words.add(a.strip())
        for r in remove:
            self.spam_words.discard(r.strip())
        if cat.lower() == "global":
            fp = "spam.txt"
            ex = self.bot_dir + "spam.txt"
        else:
            fp = self.bot_dir + "spam.txt"
            ex = "spam.txt"
        with open(ex, "r", encoding="utf-8") as f:
            ex_set = set(f.read().strip().split("\n"))
        spam_set2 = copy.deepcopy(self.spam_words)
        new_set = spam_set2 - ex_set
        with open(fp, "w", encoding="utf-8") as f:
            f.write("\n".join(new_set))
        self.update_spam()
    
    def __edit_alert(self, add:set=set(), remove:set=set(), **kwargs):
        for a in add:
            self.alert_words.add(a)
        for r in remove:
            self.alert_words.discard(r)
        fp = self.bot_dir + "alert.txt"
        with open(fp, "w", encoding="utf-8") as f:
            f.write("\n".join(self.alert_words))
        self.update_alert()

    ## send/edit/del normal msg
    async def send_msg(self, msg:discord.Message, * , op:str="op3"):
        content = msg.content.split("\n")
        match = re.search(r"\d+", content[0])
        if match is not None:
            ch_id = int(match.group(0))
        else:
            # Channel not specified
            await msg.channel.send(log_format.channel_not_specified)
            return None
        ch = self.client.get_channel(ch_id)
        if ch is None:
            # channel id is different
            await msg.channel.send(log_format.channel_different)
            return None
        if not self.check_permission_send_msg(ch, ch.guild.get_member(self.client.user.id)):
            # can't send message
            await msg.channel.send(log_format.cmd_nopermissions.format(words.send_messages))
            return None
        try:
            content = "\n".join(content[1:])
        except:
            content = None
        accept_count = cancel_count = 1
        check_content = log_format.send_message.format(
            ch_id = ch_id,
            file_count = str(len(msg.attachments)),
            content = content,
            op_level = self.op_role_mention[op],
            accept_count = str(accept_count),
            cancel_count = str(cancel_count)
        )
        check = await self.check_execute_cmd(msg, accept_count, cancel_count, content=check_content, role=self.config["op"][op])
        if check:
            # accept
            await msg.channel.send(log_format.cmd_accept)
        else:
            # cancel
            await msg.channel.send(log_format.cmd_cancel)
            return None
        file_list = self.transfer_files(msg)
        send_message = await ch.send(content)
        await self.send_files(ch, file_list)
        result = log_format.send_message_result.format(
            server = send_message.channel.guild.id,
            ch = send_message.channel.id,
            msg = send_message.id
        )
        await msg.channel.send(result)
        
    async def edit_msg(self, msg:discord.Message, dm:bool=False, * , op:str="op3"):
        content_list = msg.content.split("\n")
        try:
            url = content_list[1]
        except:
            #url is not found
            await msg.channel.send(log_format.msg_not_specified)
            return None
        if dm:
            pattern = r"@me/\d+/\d+"
        else:
            pattern = r"\d+/\d+/\d+"
        match = re.search(pattern, url)
        if match:
            server_id, ch_id, msg_id = self.split_msg_url(match.group(0))
        else:
            #not match
            await msg.channel.send(log_format.msg_not_specified)
            return None
        try:
            target = await self.search_message(ch_id, msg_id)
        except:
            await msg.channel.send(log_format.msg_get_error)
        if target.author != self.client.user:
            #target message author is not bot.
            await msg.channel.send(log_format.msg_author_different)
            return None
        try:
            content = "\n".join(content_list[2:])
        except:
            # content is None
            await msg.channel.send(log_format.msg_not_difinition)
            return None
        #check
        accept_count = cancel_count = 1
        check_content = log_format.edit_message.format(
            server = server_id,
            ch = ch_id,
            msg = msg_id,
            content = content,
            op_level = self.op_role_mention[op],
            accept_count = str(accept_count),
            cancel_count = str(cancel_count)
        )
        check = await self.check_execute_cmd(msg, accept_count, cancel_count, content=check_content, role=self.config["op"][op])
        if check:
            # accept
            await msg.channel.send(log_format.cmd_accept)
        else:
            # cancel
            await msg.channel.send(log_format.cmd_cancel)
            return None
        try:
            await target.edit(content=content)
            await msg.channel.send(log_format.edit_message_success)
            return None
        except:
            await msg.channel.send(log_format.cmd_fail)
            return None

    async def send_files(self, ch:discord.abc.GuildChannel, file_list:list):
        for fl in file_list:
            if fl["type"] == "url":
                await ch.send(fl["url"])
            elif fl["type"] == "file":
                send_file = discord.File(fp=fl["fp"])
                await ch.send(file=send_file)
                #delete tmp file
                os.remove(fl["fp"])

    def split_msg_url(self, string:str):
        return (int(n) for n in string.split("/"))
        
    async def search_message(self, ch_id, msg_id):
        data = await self.client.http.get_message(ch_id, msg_id)
        channel = self.client.get_channel(ch_id)
        return self.client._connection.create_message(channel=channel, data=data)

    def transfer_files(self, msg:discord.Message) -> list:
        if not len(msg.attachments) > 0:
            return list()
        opener = urllib.request.build_opener()
        opener.addheaders=[("User-Agent", "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:47.0) Gecko/20100101 Firefox/47.0")]
        urllib.request.install_opener(opener)
        file_list = list()
        for attachment in msg.attachments:
            url = attachment.proxy_url
            info = dict()
            if attachment.size < 8*1024*1024:
                file_name = self.tmp + attachment.filename
                info["type"] = "file"
                info["fp"] = file_name
                urllib.request.urlretrieve(url=url, filename=file_name) # save file.
            else:
                info["type"] = "url"
                info["url"] = url
            file_list.append(info)
        del opener
        return file_list

    ## send-dm/edit-dm/del-dm
    async def send_dm(self, msg:discord.Message, *, op:str="op2"):
        content_list = msg.content.split("\n")
        match = re.search(r"\d+", content_list[0])
        if match is not None:
            user_id = int(match.group(0))
        else:
            # Channel not specified
            await msg.channel.send(log_format.user_not_specified)
            return None
        member = msg.guild.get_member(user_id)
        if member is None:
            await msg.channel.send(log_format.user_not_found)
        try:
            content = "\n".join(content_list[1:])
        except:
            content = None
        accept_count = cancel_count = 1
        check_content = log_format.send_dm.format(
            user = self.save_author_mention(member),
            file_count = str(len(msg.attachments)),
            content = content,
            op_level = self.op_role_mention[op],
            accept_count = str(accept_count),
            cancel_count = str(cancel_count)
        )
        check = await self.check_execute_cmd(msg, accept_count, cancel_count, content=check_content, role=self.config["op"][op])
        if check:
            # accept
            await msg.channel.send(log_format.cmd_accept)
        else:
            # cancel
            await msg.channel.send(log_format.cmd_cancel)
            return None
        file_list = self.transfer_files(msg)
        try:
            send_message = await self.send_dm_message(user_id=member.id, content=content)
            await self.send_files(send_message.channel, file_list)
            result = log_format.send_message_result.format(
                server = "@me",
                ch = send_message.channel.id,
                msg = send_message.id
            )
        except Exception as e:
            print(e)
            result = log_format.send_dm_fail
        finally:
            await msg.channel.send(result)

    async def del_dm(self, msg:discord.Message, *, op:str="op2"):
        content_list = msg.content.split("\n")
        try:
            url = content_list[1]
        except:
            #url is not found
            await msg.channel.send(log_format.msg_not_specified)
            return None
        match = re.search(r"@me/\d+/\d+", url)
        if match:
            server_id, ch_id, msg_id = self.split_msg_url(match.group(0))
        else:
            #not match
            await msg.channel.send(log_format.msg_not_specified)
            return None
        try:
            target = await self.search_message(ch_id, msg_id)
        except:
            await msg.channel.send(log_format.msg_get_error)
        if target.author != self.client.user:
            #target message author is not bot.
            await msg.channel.send(log_format.msg_author_different)
            return None
        accept_count = cancel_count = 1
        check_content = log_format.delete_dm.format(
            ch = target.channel.id,
            msg = target.id,
            content = target.content,
            op_level = self.op_role_mention[op],
            accept_count = str(accept_count),
            cancel_count = str(cancel_count)
        )
        check = await self.check_execute_cmd(msg, accept_count, cancel_count, content=check_content)
        if check:
            # accept
            await msg.channel.send(log_format.cmd_accept)
        else:
            # cancel
            await msg.channel.send(log_format.cmd_cancel)
            return None
        try:
            await target.delete()
            await msg.channel.send(log_format.del_message_success)
        except:
            await msg.channel.send(log_format.del_message_fail)

    ##user
    async def user(self, msg:discord.Message, *, op:str="op2"):
        match = re.search(r"\d+", msg.content)
        if match is None:
            await msg.channel.send(log_format.user_not_specified)
            return None
        try:
            user = await self.client.fetch_user(int(match.group(0)))
        except:
            await msg.channel.send(log_format.user_not_found)
            return None
        content = log_format.get_user_info_result.format(
            user_id = user.id,
            user_name = self.save_author(user),
            bot = str(user.bot),
            created_at = user.created_at.strftime("%Y/%m/%d %H:%M:%S"),
            avatar = user.avatar_url,
            server = self.server_member(user, msg.guild)
        )
        await msg.channel.send(content)
    
    def server_member(self, user:discord.User, server:discord.Guild):
        member = server.get_member(user.id)
        if member is None:
            return str(False)
        else:
            return log_format.user_is_server_member.format(
                server = str(True),
                nick = str(member.nick),
                join = member.joined_at.strftime("%Y/%m/%d %H:%M:%S"),
                roles = "\n\t".join([self.save_role(r) for r in member.roles])
            )

    async def user_exist(self, user_id:str) -> bool:
        try:
            await self.client.fetch_user(user_id)
            return True
        except:
            return False

    ## stop
    async def stop(self, msg:discord.Message, * , op:str="op2"):
        #search target users
        targets = re.findall(r"\d+", msg.content, re.S)
        server = msg.guild
        result = list()
        for target in targets:
            member = server.get_member(int(target))
            if member is not None:
                await self.add_roles(member, {self.config["stop"]}, server.id)
                result.append(member)
        content = log_format.stop_result.format(users="\n".join([self.save_author_mention(m) for m in result]))
        await msg.channel.send(content)

    ## get log
    async def get_msg_log(self, msg:discord.Message, dm:bool=False, *, op:str="op3"):
        match = re.search(r"\d+", msg.content.split("\n")[0])
        if match is not None:
            ch_id = int(match.group(0))
        else:
            # Channel not specified
            content = log_format.user_not_specified if dm else log_format.channel_not_specified
            await msg.channel.send(content)
            return None
        if dm:
            check = await self.user_exist(ch_id)
            if check:
                ch = await self.get_user_private_channel_by_id(ch_id)      
            else:
                await msg.channel.send(log_format.user_different)
        else:
            ch = self.client.get_channel(ch_id)
        if ch is None:
            # channel id is different
            content = log_format.private_ch_not_found if dm else log_format.channel_different
            await msg.channel.send(content)
            return None
        if isinstance(ch, (discord.VoiceChannel, discord.VoiceChannel)):
            #channel type is voice or category
            await msg.channel.send(log_format.channel_not_text)
            return None
        if not dm:
            if not self.check_permission_read_message_history(ch, ch.guild.get_member(self.client.user.id)):
                # can't read message
                await msg.channel.send(log_format.cmd_nopermissions.format(words.read_message_history))
                return None
        
        await msg.channel.send(log_format.cmd_accept)
        # cmd start
        kwargs = self.spilit_function(msg.content, 2)
        fp, result = await self.logs_from(ch, **kwargs)
        send_file = discord.File(fp=fp)
        await msg.channel.send(result, file=send_file)
        os.remove(fp) #remove file
        return None

    async def logs_from(self, channel:discord.abc.GuildChannel, limit:str="100", reverse:str="true", encoding:str="utf-8", **kwargs) -> str:
        start_time = datetime.datetime.now()
        limit = int(limit)
        reverse = False if reverse.lower().strip() == "false" else True
        before = await self.get_datetime_or_message(channel, kwargs.get("before"))
        after  = await self.get_datetime_or_message(channel, kwargs.get("after"))
        around = await self.get_datetime_or_message(channel, kwargs.get("around"))
        fp = self.tmp + "msg_log.txt"
        counter = {"MsgCount": 0, "UserIDs" : set()}
        with open(fp, "w", encoding=encoding) as f:
            async for msg in channel.history(limit=limit, before=before, after=after, around=around, oldest_first=reverse):
                f.write(self.save_msg_log(msg, write=False))
                self.logs_counter(msg, counter)
        logs_result = log_format.msg_log_result.format(
            channel = self.save_channel(channel),
            msg_count = str(counter["MsgCount"]),
            user_count = str(len(counter["UserIDs"])),
            limit = str(limit),
            before = self.log_reesult_msg_or_datetime(before),
            after  = self.log_reesult_msg_or_datetime(after),
            around = self.log_reesult_msg_or_datetime(around),
            reverse = str(reverse),
            encoding = encoding,
            start_time = start_time.strftime("%Y/%m/%dT%H:%M:%S"),
            finish_time = datetime.datetime.now().strftime("%Y/%m/%dT%H:%M:%S")
        )
        fp = self.insert_file_head((logs_result + "\n" + "-"*75 + "\n"), fp, encoding=encoding)
        return fp, logs_result

    def logs_counter(self, msg:discord.Message, counter:dict) -> dict:
        counter["MsgCount"] += 1
        counter["UserIDs"].add(str(msg.author.id))

    async def get_datetime_or_message(self, ch:discord.abc.GuildChannel, string:str):
        if string is None:
            return None
        try:
            r = datetime.datetime.strptime(string, "%Y/%m/%dT%H:%M:%S")
        except:
            try:
                r = await self.search_message(ch.id, int(string))
            except:
                r = None
        finally:
            return r

    def log_reesult_msg_or_datetime(self, target) -> str:
        if isinstance(target, discord.Message):
            return log_format.msg_url.format(
                server = "@me" if target.guild is None else target.guild.id,
                ch = target.channel.id,
                msg = target.id
            )
        elif isinstance(target, datetime.datetime):
            return target.strftime("%Y/%m/%dT%H:%M:%S")
        else:
            return words.unspecified

    async def ls(self, msg:discord.Message, op="op2"):
        await msg.channel.send(cmd_msg.ls.format(bot=self.config["NAME"]))

    async def system_message(self, msg:discord.Message, * , op:str="op3"):
        content_list = msg.content.split("\n")
        try:
            action = content_list[0].split()[1].strip().lower()
        except:
            action = "show"
        try:
            fp = self.bot_dir + content_list[1].lstrip("fp= ./").strip()
            if not os.path.exists(fp):
                await msg.channel.send(log_format.file_is_not_exit)
                return None
        except:
            await msg.channel.send(log_format.filepath_not_specified)
            return None
        if action == "edit":
            if len(msg.attachments) > 0:
                url = msg.attachments[0].proxy_url
                copy_fp = self.update_system_message(fp, url=url)
            else:
                try:
                    content = "\n".join(content_list[2:])
                except:
                    await msg.channel.send(log_format.new_content_not_specified)
                    return None
                copy_fp = self.update_system_message(fp, content = content)
            await self.edit_system_message_report(msg.channel, fp, copy_fp)
        else:
            await self.show_system_message(msg.channel, fp)
    
    def update_system_message(self, fp, content:str=None, url:str=None) -> str:
        copy_fp = self.tmp + fp.split("/")[-1]
        shutil.copy(fp, copy_fp)
        if url is not None:
            self.save_file(url, fp)
        elif content is not None:
            with open(fp, "w", encoding="utf-8") as f:
                f.write(content)
        else:
            pass
        return copy_fp

    async def edit_system_message_report(self, ch:discord.abc.GuildChannel, fp:str, copy_fp:str):
        with open(fp, "r", encoding="utf-8") as f:
            content = f.read()
        send_file = discord.File(fp=fp)
        await ch.send(content, file=send_file)

    async def show_system_message(self, ch:discord.abc.GuildChannel, fp:str):
        with open(fp, "r", encoding="utf-8") as f:
            content = f.read()
        try:
            await ch.send(content)
        except:
            f = discord.File(fp=fp)
            await ch.send(content=fp, file=f)

    ## receive dm
    async def receive_dm(self, msg:discord.Message):
        content = log_format.receive_dm.format(
            author = self.save_author_mention(msg.author),
            time = datetime.datetime.now().strftime("%Y/%m/%d %H:%M:%S"),
            ch = msg.channel.id,
            msg = msg.id,
            content = msg.content
        )
        ch = self.client.get_channel(self.config["receive_dm_ch"])
        await ch.send(content)
        file_list = self.transfer_files(msg)
        await self.send_files(ch, file_list)

    async def receive_dm_edit(self, before:discord.abc.GuildChannel, after:discord.abc.GuildChannel):
        content = log_format.recieve_dm_edit.format(
            author = self.save_author_mention(after.author),
            time = datetime.datetime.now().strftime("%Y/%m/%d %H:%M:%S"),
            ch = after.channel.id,
            msg = after.id,
            before = before.content,
            after = after.content
        )
        ch = self.client.get_channel(self.config["receive_dm_ch"])
        await ch.send(content)
        file_list = self.transfer_files(after)
        await self.send_files(ch, file_list)
    
    async def receive_dm_delete(self, msg:discord.Message):
        content = log_format.receive_dm_delete.format(
            author = self.save_author_mention(msg.author),
            time = datetime.datetime.now().strftime("%Y/%m/%d %H:%M:%S"),
            ch = msg.channel.id,
            msg = msg.id,
            content = msg.content
        )
        ch = self.client.get_channel(self.config["receive_dm_ch"])
        await ch.send(content)
        file_list = self.transfer_files(msg)
        await self.send_files(ch, file_list)

    ## Control Role
    async def replace_role(self, user_id:int, new_roles, server_id:int=None):
        server_id = self.config["action_server_id"] if server_id is None else server_id
        payload = {'roles': tuple(new_roles)}
        await self.client.http.edit_member(server_id, user_id, reason=None, **payload)
    
    async def add_roles(self, member:discord.Member, roles:set, server_id:int=None):
        member_roles = {r.id for r in member.roles}
        new_roles = list(member_roles.union(roles))
        await self.replace_role(member.id, new_roles, server_id)

    async def add_role(self, member:discord.Member, role_id:int, server_id:int=None):
        member_roles = {r.id for r in member.roles}
        member_roles.add(role_id)
        await self.replace_role(member.id, member_roles, server_id)
    
    async def remove_role(self, member:discord.Member, role_id:int, server_id:int=None):
        member_roles = {r.id for r in member.roles}
        member_roles.discard(role_id)
        await self.replace_role(member.id, member_roles, server_id)

    async def role_control(self, msg:discord.Message, *, op:str="op1"):
        if msg.content.startswith("+color"):
            name = msg.content.strip("+color ").split().pop(0)
            try:
                target = self.color_role[name]
            except:
                await msg.channel.send(log_format.role_not_found)
                return None
            member_roles = {r.id for r in msg.author.roles}
            new_roles = self.exclusion_role(member_roles, self.color_role_set)
            new_roles.add(target)
            await self.replace_role(msg.author.id, list(new_roles))
            result = log_format.role_color_changed.format(msg.author.id, name)
            await msg.channel.send(result)
        elif msg.content.startswith("+"):
            targets = msg.content.lstrip("+").strip().split()
            add_roles = set()
            for target in targets:
                role_id = self.normal_role.get(target)
                if role_id is not None:
                    add_roles.add(role_id)
            member_roles = {r.id for r in msg.author.roles}
            new_roles = member_roles.union(add_roles)
            await self.replace_role(msg.author.id, list(new_roles))
            result = log_format.role_changed.format(msg.author.id)
            member = await msg.guild.fetch_member(msg.author.id)
            embed = self.report_user_role_embed(member)
            await msg.channel.send(result, embed=embed)
        elif msg.content.startswith("-color"):
            member_roles = {r.id for r in msg.author.roles}
            new_roles = member_roles - self.color_role_set
            await self.replace_role(msg.author.id, list(new_roles))
            result = log_format.role_color_reset.format(msg.author.id)
            await msg.channel.send(result)
        elif msg.content.startswith("-"):
            targets = msg.content.lstrip("-").strip().split()
            remove_roles = set()
            for target in targets:
                role_id = self.normal_role.get(target)
                if role_id is not None:
                    remove_roles.add(role_id)
            member_roles = {r.id for r in msg.author.roles}
            new_roles = member_roles - remove_roles
            await self.replace_role(msg.author.id, list(new_roles))
            result = log_format.role_changed.format(msg.author.id)
            member = await msg.guild.fetch_member(msg.author.id)
            embed = self.report_user_role_embed(member)
            await msg.channel.send(result, embed=embed)
        else:
            return None

    def exclusion_role(self, roles:set, targets:set) -> set:
        return (roles - targets)

    def report_user_role_embed(self, member:discord.Member) -> discord.Embed:
        roles = "\n".join([("  ・" + r.name) for r in member.roles])
        em = discord.Embed(type = "rich", description = log_format.role_list.format(roles), color=member.color)
        if member.nick is None:
            name = member.name
        else:
            name = member.nick
        em.set_author(name = name, icon_url=member.avatar_url)
        return em

    def raw_add_emoji_role_control(self, payload:discord.RawReactionActionEvent):
        pass

    async def block_cmd(self, msg: discord.Message, *, op: str="op3"):
        match = re.search(r"\d+", msg.content)
        if match is None:
            await msg.channel.send(log_format.user_not_specified)
            return None
        try:
            user = await self.client.fetch_user(int(match.group(0)))
        except:
            await msg.channel.send(log_format.user_not_found)
            return None
        accept_count = cancel_count = 1
        check_content = log_format.block_user_check.format(
            mention = user.mention,
            user_name = user.name,
            user_id = str(user.id),
            op_level = self.op_role_mention[op],
            accept_count = str(accept_count),
            cancel_count = str(cancel_count)
        )
        check = await self.check_execute_cmd(msg, accept_count, cancel_count, content=check_content, role=self.config["op"][op])
        if check:
            # accept
            await msg.channel.send(log_format.cmd_accept)
        else:
            # cancel
            await msg.channel.send(log_format.cmd_cancel)
            return None
        try:
            await user.block()
        except Exception as e:
            #error
            await msg.channel.send(log_format.block_user_fail.format(str(e)))
            return
        await msg.channel.send(log_format.block_user)
        await self.admin_action_ch.send(
            log_format.block_user_result.format(
                mention = user.mention,
                user_name = user.name,
                user_id = str(user.id)
            )
        )
    
    async def unblock_cmd(self, msg: discord.Message, *, op: str="op3"):
        match = re.search(r"\d+", msg.content)
        if match is None:
            await msg.channel.send(log_format.user_not_specified)
            return None
        try:
            user = await self.client.fetch_user(int(match.group(0)))
        except:
            await msg.channel.send(log_format.user_not_found)
            return None
        try:
            await user.unblock()
        except Exception as e:
            #error
            await msg.channel.send(log_format.unblock_user_fail.format(str(e)))
            return
        await msg.channel.send(log_format.unblock_user)
        await self.admin_action_ch.send(
            log_format.unblock_user_result.format(
                mention = user.mention,
                user_name = user.name,
                user_id = str(user.id)
            )
        )

    ## cmd check
    async def check_execute_cmd(self, msg:discord.Message, done_count:int=1, cancel_count:int=1, **kwargs) -> bool:
        timeout = 300 if kwargs.get("timeout") is None else kwargs["timeout"]
        cmder = msg.author
        cmd_role = self.config["op"]["op2"] if kwargs.get("role") is None else kwargs["role"]
        if kwargs.get("content") is not None:
            msg = await msg.channel.send(kwargs["content"])
        await msg.add_reaction("⭕")
        await msg.add_reaction("❌")

        def check(reaction:discord.Reaction, user:discord.User):
            if user == self.client.user:
                return False
            member = reaction.message.guild.get_member(user.id)
            if member is None:
                return False
            return cmd_role in {r.name for r in member.roles}
        
        emoji_count = {"done" : 0, "cancel" : 0}
        loop = True
        while loop:
            rec, user = await self.client.wait_for('reaction_add', timeout=timeout, check=check)
            if str(rec.emoji) == "⭕":
                emoji_count["done"] += 1
                if emoji_count["done"] >= done_count:
                    break
            elif str(rec.emoji) == "❌":
                emoji_count["cancel"] += 1
                if emoji_count["cancel"] >= cancel_count:
                    loop = False
            else:
                continue
        else:
            # cmd cancel
            return False
        # cmd accept
        return True

    #translation bot
    async def translation_bot(self, msg:discord.Message):
        content = msg.content.lstrip(cmd_trigger.translation[0]) # remove trigger word
        content_list = content.split(" ")
        target = content_list.pop(0) # pop target language
        content = " ".join(content_list) #join content list
        results = self.translate(content, target)
        embed = self.translate_embed(results, content, msg)
        await msg.channel.send(results[0], embed=embed)
    
    def translate_embed(self, results:tuple, content:str, msg:discord.Message) -> discord.Embed:
        """
        @para results:tuple (result, target, source, confidence)
        """
        color = msg.author.color if msg.author.color != discord.Colour.default() else discord.Colour(self.bot_color)
        embed = discord.Embed(
            type = "rich",
            timestamp = msg.created_at,
            description = content[0:30] + ("..." if len(content) >= 30 else ""),
            color = color
        )
        embed.set_author(name = self.user_name(msg.author), icon_url=msg.author.avatar_url)
        # embed.set_author(name = self.user_name(msg.author))
        embed.set_footer(text = "translation: {0} → {1}. language detection confidence: {2}%".format(results[2], results[1], results[3]))
        return embed

    async def auto_translation(self, msg:discord.Message):
        detect_sample = msg.content.split("\n")[0]
        source, confidence = self.detect(detect_sample)
        if source == self.config["auto_translation_mainlang"]:
            target = self.config["auto_translation_targetlang"]
        else:
            target = self.config["auto_translation_mainlang"]
        result = self.translation(msg.content, target, source)
        results = result, target, source, confidence
        embed = self.translate_embed(results, msg.content, msg)
        await msg.channel.send(results[0], embed=embed)

    #minesweeper
    async def minesweeper_bot(self, msg:discord.Message):
        c_list = msg.content.split("\n")[0].split()
        try:
            bomb = int(c_list[1])
        except:
            bomb = 10
        try:
            fild = c_list[2]
            fild_list = fild.split("x")
            col = int(fild_list[0])
            row = int(fild_list[1])
        except:
            col = row = 10
        content = self.minesweeper(bomb, col, row)
        await msg.channel.send(content)

    #poll
    async def poll(self, msg: discord.Message):
        pol_chrs = ["🔴", "🟢", "🟠", "🔵", "🟤", "🟡", "🟣", "🟥", "🟩", "🟧", "🟦", "🟫", "🟨", "🟪", "🔶", "🔷", "🔺", "🔻", "⏺", "⏹"]
        pol_yn = ["✅", "❌"]
        pol_yn_str = ["はい/yes", "いいえ/no"]
        items = re.findall(r'\".*?\"', msg.content)
        q = "❓" + " ".join(msg.content.split('"')[0].split(" ")[1:])
        count = len(items)
        if count < 0:
            await msg.channel.send(log_format.poll_err_noitem)
            return
        elif count == 0:
            #yes/no
            reac = pol_yn
            nl = list()
            for n in range(0, 2):
                nl.append(pol_yn[n] + pol_yn_str[n])
            content = "\n".join(nl)
        elif count > 20:
            #over
            await msg.channel.send(log_format.poll_err_over)
            return
        else:
            #nomal
            reac = pol_chrs[:count]
            nl = list()
            for n in range(0, count):
                item = items[n].replace("\n", " ")
                nl.append(pol_chrs[n] + items[n].strip('"'))
            content = "\n".join(nl)
        em = discord.Embed(
            type = "rich",
            color=msg.author.color,
            timestamp=msg.created_at,
            description=content
        )
        em.set_author(
            name = self.user_name(msg.author),
            icon_url = msg.author.avatar_url
        )
        target = await msg.channel.send(q, embed=em)
        for r in reac:
            await target.add_reaction(r)

    #roulette
    async def roulette(self, message: discord.Message):
        #cmd start
        channel = message.channel
        lines = message.content.split("\n")
        line1 = lines.pop(0)
        items_text = "\n".join(lines)
        items = items_text.strip().split("\n")
        items_count = len(items)
        extract_text = line1.strip(cmd_trigger.roulette[0])
        try:
            extract = int(extract_text)
        except:
            extract = 1
        finally:
            if extract < 1:
                extract = 1
            elif extract > items_count:
                extract = items_count
            else:
                pass
        #send check message
        msg = await channel.send(log_format.roulette_start_content.format(items_count, extract))
        await msg.add_reaction("✅")
        await msg.add_reaction("❌")

        def check(reaction:discord.Reaction, user:discord.User):
            if user == self.client.user:
                return False
            if str(reaction.emoji) in ("✅", "❌"):
                return True
            return False
        
        rec, user = await self.client.wait_for('reaction_add', timeout=300, check=check)
        if str(rec.emoji) == "✅":
            #start
            pass
        else:
            #cancel
            await channel.send(log_format.roulette_cancel_content)
            return
        content = log_format.roulette_result.format("\n".join(random.sample(items, extract)))
        await channel.send(content)

    #donate system from suiseicord
    async def donation(self, payload:discord.RawReactionActionEvent):
        if str(payload.emoji) != self.donate_emoji:
            return None
        if payload.channel_id != self.donate_channel:
            return None
        if payload.message_id in self.donate_msgs:
            await self.send_donation(payload.member)
            return None
        #get target message
        ch = self.client.get_channel(payload.channel_id)
        msg = await ch.fetch_message(payload.message_id)
        if self.donate_word in msg.content:
            #add donate message_id list
            self.donate_msgs.append(payload.message_id)
            await self.send_donation(payload.member)
        return None
    
    async def send_donation(self, member:discord.Member):
        url = self.create_donate_formlink(member)
        fp = self.sys_msg_dir + "donate_guide.txt"
        with open(fp, "r", encoding="utf-8") as f:
            content = f.read()
        content = content.replace("<URL>", url)
        try:
            await self.send_dm_message(member.id, content)
            #report
            await self.donate_report.send(log_format.donate_report_success.format(self.save_author(member)))
        except Exception as e:
            #report fail
            await self.donate_report.send(log_format.donate_report_fail.format(self.save_author(member)))
            

    def create_donate_formlink(self, user:discord.User):
        query = {
            "entry.{}".format(self.donate_entrys["id"]) : user.id,
            "entry.{}".format(self.donate_entrys["name"]) : str(user)
        }
        return '%s?%s' % (self.donate_formlink, urlencode(query))

    #Basic function
    def user_name(self, author):
        if isinstance(author, discord.Member):
            if author.nick is not None:
                return author.nick
        return author.name

    def change_color_code(self):
        RGB = self.config["color"] #list
        return (RGB[0]*256*256 + RGB[1]*256 + RGB[2])

    def insert_file_head(self, insert_content:str, fp:str, * , new_fp:str=None, encoding:str="utf-8") -> str:
        if new_fp is None:
            new_fp = fp #copy file name
            fp = fp + "dump" #new file name
            if os.path.exists(fp):
                os.remove(fp)
            os.rename(new_fp, fp) #rename to dump file
        with open(new_fp, "w", encoding=encoding) as nf:
            nf.write(insert_content + "\n") #insert
            with open(fp, "r", encoding=encoding) as f:
                line = f.readline()
                while line:
                    nf.write(line) # copy file content
                    line = f.readline()
        os.remove(fp) # remove dump file
        return new_fp

    def spilit_function(self, content, start_line=1, argument=None, punctuation="=", * , split="\n", rest_return=True):
        return_dict = dict()
        content_list = content.split(split)
        if start_line >= 2:
            if rest_return:
                return_dict["rest_first"] = split.join(content_list[:(start_line - 1)])
            else:
                pass
            del content_list[:(start_line - 1)]
        else:
            pass
        if argument is None:
            num = 0
            for cl in content_list:
                if punctuation in cl:
                    cll = cl.split(punctuation)
                    return_dict[cll[0].strip()] = punctuation.join(cll[1:]).strip()
                    num += 1
                else:
                    break
            del content_list[:num]
            if rest_return:
                return_dict["rest_last"] = split.join(content_list)
            else:
                pass
            return return_dict
        elif isinstance(argument, str):
            num = 1
            for cl in content_list:
                if argument in cl.split(punctuation):
                    return_dict[argument] = punctuation.join(cl.split(punctuation)[1:])
                    del content_list[:num]
                    break
                else:
                    num += 1
            if rest_return:
                return_dict["rest_last"] = split.join(content_list)
            else:
                pass
            return return_dict
        elif isinstance(argument, (list, set, tuple)):
            num = 0
            num_else = 0
            for cl in content_list:
                cll = cl.split(punctuation)
                if cll[0] in argument:
                    return_dict[cll[0]] = punctuation.join(cll[1:])
                    num += 1
                    num += num_else
                    num_else = 0
                else:
                    num_else += 1
            del content_list[:num_else]
            if rest_return:
                return_dict["rest_last"] = split.join(content_list)
            else:
                pass
            return return_dict
        else:
            return dict()

    async def report_developer(self, msg:discord.Message):
        content = log_format.report_developer.fromat(
            msg_id = msg.id,
            time = msg.timestamp.strftime("%Y/%m/%d %H:%M:%S"),
            edit_time = msg.edited_timestamp.strftime("%Y/%m/%d %H:%M:%S") if isinstance(msg.edited_timestamp, datetime,datetime) else "not editd",
            type = str(msg.type),
            server = "{0} (ID: {1})".format(msg.guild.name, msg.guild.id),
            channel = "{0} (ID: {1})".format(msg.channel.name, msg.channel.id),
            author = self.save_author_mention(msg.author),
            embeds = "",
            attachiments = "",
            mentions = "",
            ch_mentions = "",
            role_mentions = "",
            content = msg.content
        )
        await self.send_dm_message(Developer.id, content)

    async def test(self, msg:discord.Message):
        pattern = "|".join(self.spam_words)
        match = re.search(pattern, msg.content)
        if not match:
            print("no match")
        else:
            print("match!")
            print(match.group())

#test
if __name__ == "__main__":
    trans = Translation()
    while True:
        target = input("target: ")
        source = input("source: ")
        content = input("content: ")
        #with open("send_msg.txt", "r", encoding="utf-8") as f:
            #content = f.read()
        trans.test_translation(content, target, source)
