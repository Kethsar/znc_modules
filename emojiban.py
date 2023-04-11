'''
    Kickbans users that post unicode emojis
    Bans last from 1 to 5 minutes, random every time
    TODO: increase min and max ban length for repeat offenders (suedoe)
'''
import math
import random
import re
import sys
import ast

try:
    import znc
except ImportError:
    print("This script must be run as a ZNC module")
    sys.exit(1)

class bantimer(znc.Timer):
    def RunJob(self):
        self.GetModule().unban(self.nick)

class emojiban(znc.Module):
    description = "Set a timed ban on a user that uses emoji"
    RADIO = '#r/a/dio'
    EXEMPT = ['edzilla', 'eiki', 'fushi', "kethbot", "kethzilla", "nisezilla", "ireul"] # bots that are not +o or above

    # I knew attempting emoticons was a bad idea...
    EMOTE_RE1 = re.compile(r'>?[：꞉∶˸։﹕:;;Xxх=][\^\'v＾-]*(\(+|\)+|D+|\[+|\]+|p+|P+|d+|ԁ+|/+|\\+|F|c+|\|+|>+|<+|）+|s+|S+|0+|o+|O+|}+)$')
    EMOTE_RE2 = re.compile(r'(\(+|\)+|D+|\[+|\]+|q+|d+|ԁ+|/+|\\+|c+|C+|\|+|>+|<+|）+|s+|S+|0+|o+|O+|{+)[\^\'v＾-]*[：꞉∶˸։﹕:;;Xxх=]<?$')
    BASE_EMOTICONS = [
        'owo',
        'OwO',
        '0w0',
        'UwU',
        'uwu',
        ';w;',
        '<_<',
        '>_>',
        '<.<',
        '>.>',
        '<w<',
        '>w>',
        'T_T',
        'T.T',
        'ToT',
        '._.',
        '-_-',
        'o_o',
        'O_O',
        'o_O',
        'O_o',
        '0_0',
        'o_0',
        '0_o',
        'O.O',
        'o.o',
        'o.O',
        'O.o',
        'o.0',
        '0.o',
        'x_x',
        'X_X',
        'x.x',
        'X.X',
        '>w<',
        '>_<',
        '>.<',
        '^^,',
        '^^;',
        '^_^',
        '^.^',
        '^w^',
        'v_v',
        'V_V',
        'v.v',
        'V.V',
        ':v',
        'v:',
        ':V',
        ':\\/',
        '\\/:',
        "n_n",
        "nwn",
        "@_@",
        "n.n",
    ]
    EMOTICONS = []
    EXCEPTIONS = [
        '=>',
        '<=',
        '>=',
        '=<',
        'xp',
        'dx',
        'xs',
        'sx',
        'xf',
        'x>',
        '<x',
        '0;',
        'ox',
        'xo',
        'ssx',
        '>x',
        'ccx',
        '\\x',
        'x\\'
    ]
    PREFIX_EXCEPTIONS = {
        'xd': [
        'pokemon',
        'springfield'
        ],
        'd:': [
            'initial'
        ]
    }
    PUNCTUATION = '!?.,\'"~'

    def OnLoad(self, args, message):
        # https://unicode-table.com/en/blocks/
        # 231A: wrist watch; 231B: hour glass; 2328: keyboard; 23F0-23F3: clock, stopwatch, timer, hour glass
        emojistr = r'[\U0000231A\U0000231B\U00002328\U000023F0-\U000023F3'
        # 2600 - 2604: sun, cloud, umbrella, snowman, comet
        # 260E, 260F: telephones; 2614-263F: various symbols with no immediate use (except maybe hammer and sickle: 262D)
        emojistr += r'\U00002600-\U00002604\U0000260E\U0000260F\U00002614-\U0000262D\U00002630-\U0000263F'
        # 2670-267F: various symbols, mostly recycling
        # 2686-2712: Various symbols, potentially okay are some pentagrams (26E4-26E7)
        emojistr += r'\U00002670-\U0000267F\U00002686-\U0000269A\U0000269C\U0000269D\U000026A0-\U000026E8\U000026EA-\U00002712'
        # 1F170 - 1FFFD: Various meme shit (bold B and other letters in a square thing), actual emoji, and other symbols
        emojistr += r'\U0001F170-\U0001FFFD]'
        self.emoji_re = re.compile(emojistr)

        for emote in self.BASE_EMOTICONS:
            self.EMOTICONS.append(emote)
            self.EMOTICONS.append(f"({emote})")
            self.EMOTICONS.append(f"[{emote}]")
            self.EMOTICONS.append(f"{{{emote}}}")

        return True
    
    def OnChanTextMessage(self, message):
        try:
            chanName = message.GetChan().GetName().lower()
            if not chanName == self.RADIO:
                return znc.CONTINUE
            
            zncnick = message.GetNick()
            nick = zncnick.GetNick()
            lnick = nick.lower()
            if self.isAdmin(zncnick) or lnick in self.EXEMPT:
                return znc.CONTINUE

            lmsg = message.GetText().lower()
            if self.emoji_re.search(lmsg):
                self.kickban(lnick, "Fuck off with your emoji (1 - 5 minute ban)")
                return znc.CONTINUE

            noctrl = re.sub(r'\x03([0-9]+(,[0-9]+)?)?', '', message.GetText())
            noctrl = re.sub(r'[\x00-\x1F]', '', noctrl)
            pieces = noctrl.split(' ')
            curidx = -1
            openPara = False
            openBracket = False

            if lnick == 'ojiisan':
                if (self.EMOTE_RE1.match(noctrl)
                    or self.EMOTE_RE2.match(noctrl)):
                    self.kick(lnick, "No emoticons")
                    self.PutModule("Kicked {0} for {1}".format(nick, pieces))
                    return znc.CONTINUE
                    
                for e in self.EMOTICONS:
                    if e in noctrl:
                        self.kick(lnick, "No emoticons")
                        self.PutModule("Kicked {0} for {1}".format(nick, e))
                        return znc.CONTINUE

            for i in range(len(pieces)):
                piece = pieces[i]

                if piece in self.EMOTICONS:
                    self.kick(lnick, "No emoticons")
                    self.PutModule("Kicked {0} for {1}".format(nick, piece))

                piece = piece.strip(self.PUNCTUATION)
                lpiece = piece.lower()
                curidx = curidx + len(piece)

                if lpiece.lower() in self.EXCEPTIONS:
                    continue
                if i > 0 and lpiece in self.PREFIX_EXCEPTIONS and pieces[i-1].lower() in self.PREFIX_EXCEPTIONS[lpiece]:
                    continue

                if piece.startswith('(') and noctrl.find(')', curidx) > 0:
                    openPara = True
                    continue
                if piece.startswith('[') and noctrl.find(']', curidx) > 0:
                    openBracket = True
                    continue

                if ')' in piece and openPara:
                    openPara = False
                    continue
                if ']' in piece and openBracket:
                    openBracket = False
                    continue

                if lpiece.endswith("'s") or lpiece.endswith("'d"):
                    continue

                # Flam and his dumb 'D: drive'
                if self.isWinDriveRoot(lpiece) and re.match(r"{0}\s*drive".format(lpiece), noctrl[curidx:], re.I):
                    continue

                if not (piece in self.EMOTICONS
                    or self.EMOTE_RE1.match(piece)
                    or self.EMOTE_RE2.match(piece)):
                    continue

                self.kick(lnick, "No emoticons")
                self.PutModule("Kicked {0} for {1}".format(nick, piece))

                break

        except Exception as err:
            self.PutModule(str(err))

        return znc.CONTINUE

    def isWinDriveRoot(self, s):
        if len(s) != 2 or not s.endswith(":"):
            return False

        if re.match('[a-z]', s):
            return True
        
        return False

    '''
    def OnModCommand(self, command):
        try:
            cmd = command.strip().lower()
            if cmd == 'getwarn':
                self.PutModule(str(self.warnings))
                return

            pieces = cmd.split(' ')
            if len(pieces) < 2 or pieces[0] != 'dewarn':
                self.PutModule("Commands: getwarn; dewarn <users...>")
                return

            dewarned = ''
            for i in range(1, len(pieces)):
                if pieces[i] in self.warnings:
                    del self.warnings[pieces[i]]
                    dewarned += pieces[i] + ", "

            dewarned = dewarned.strip(', ')
            if len(dewarned) > 0:
                self.nv['warnings'] = str(self.warnings)
                self.PutModule("Removed {0} from warnings".format(dewarned))
        except Exception as err:
            self.PutModule("OnModCommand Exception: " + str(err))
    '''

    def kickban(self, user, msg):
        try:
            btime = math.floor(random.random() * 5 * 60)
            if btime < 60:
                btime = 60
            
            timer = self.CreateTimer(bantimer, interval=btime, label=user)
            timer.nick = user

            self.PutIRC("MODE {0} +b {1}!*@*".format(self.RADIO, user))
            self.kick(user, msg)
            self.PutModule("Banned {0} for {1} seconds".format(user, btime))
        except Exception as err:
            self.PutModule("kickban Exception: " + str(err))

    def kick(self, user, msg):
        try:
            self.PutIRC("KICK {0} {1} :{2}".format(self.RADIO, user, msg))
        except Exception as err:
            self.PutModule("kick Exception: " + str(err))

    def unban(self, user):
        try:
            self.PutIRC("MODE {0} -b {1}!*@*".format(self.RADIO, user))
        except Exception as err:
            self.PutModule("unban Exception: " + str(err))
    
    def inRadio(self):
        try:
            radioChan = self.GetNetwork().FindChan(self.RADIO)

            if radioChan:
                return True
            else:
                return False
        except Exception as err:
            self.PutModule("inRadio Exception: " + str(err))

    def sendIfInRadio(self, message):
        try:
            if self.inRadio():
                self.sendMessage(self.RADIO, message)
        except Exception as err:
            self.PutModule("sendIfInRadio Exception: " + str(err))
    
    def sendMessage(self, ctx, msg):
        try:
            user = self.GetUser()
            nick = self.GetModNick()

            if user:
                nick = user.GetNick()

            self.PutIRC("PRIVMSG {0} :{1}".format(ctx, msg))
            self.PutUser(":{0} PRIVMSG {1} :{2}".format(nick, ctx, msg))
        except Exception as err:
            self.PutModule("sendMessage Exception: " + str(err))

    def isAdmin(self, zncnick):
        return (zncnick.HasPerm("@") or 
                zncnick.HasPerm("&") or
                zncnick.HasPerm("~"))