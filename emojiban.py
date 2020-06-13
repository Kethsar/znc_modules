'''
	Kickbans users that post unicode emojis
	Bans last from 1 to 5 minutes, random every time
	TODO: increase min and max ban length for repeat offenders (suedoe)
'''
import math
import random
import re
import sys

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
	EXEMPT = ['edzilla', 'eiki', 'fushi'] # bots that are not +o or above

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

		return True
	
	def OnChanTextMessage(self, message):
		try:
			chanName = message.GetChan().GetName().lower()
			if not chanName == self.RADIO:
				return znc.CONTINUE
			
			zncnick = message.GetNick()
			nick = zncnick.GetNick().lower()
			if self.isAdmin(zncnick) or nick in self.EXEMPT:
				return znc.CONTINUE

			lmsg = message.GetText().lower()
			if self.emoji_re.search(lmsg):
				self.kickban(nick)

		except Exception as err:
			self.PutModule(str(err))

		return znc.CONTINUE

	def OnModCommand(self, command):
		try:
			self.PutModule("Nothing here")
		except Exception as err:
			self.PutModule("OnModCommand Exception: " + str(err))

	def kickban(self, user):
		try:
			btime = math.floor(random.random() * 5 * 60)
			if btime < 60:
				btime = 60
			
			timer = self.CreateTimer(bantimer, interval=btime)
			timer.nick = user
			msg = "Fuck off with your emoji (1 - 5 minute ban)"

			self.PutIRC("MODE {0} +b {1}!*@*".format(self.RADIO, user))
			self.PutIRC("KICK {0} {1} :{2}".format(self.RADIO, user, msg))
			self.PutModule("Banned {0} for {1} seconds".format(user, btime))
		except Exception as err:
			self.PutModule("kickban Exception: " + str(err))

	def unban(self, user):
		try:
			self.PutIRC("MODE {0} -b {1}!*@*".format(self.RADIO, user))
		except Exception as err:
			self.PutModule("unban Exception: " + str(err))

	def isAdmin(self, zncnick):
		return (zncnick.HasPerm("@") or 
				zncnick.HasPerm("&") or
				zncnick.HasPerm("~"))