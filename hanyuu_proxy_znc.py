'''
	This script gives a way for r/a/dio DJs to use Hanyuu without being given +h
'''
import sys
import re

try:
	import znc
except ImportError:
	print("This script must be run as a ZNC module")
	sys.exit(1)

class auth_timer (znc.Timer):
	nick = ""

	def RunJob(self):
		self.GetModule().deauthNick(self.nick)

class hanyuu_proxy_znc(znc.Module):
	description = "Acts as a proxy for some Hanyuu commands. ZNC version"

	RADIO = "#r/a/dio"
	NICKSERV = "nickserv"
	DJDICT = {
		"authed": False,
		"timeout": None,
		"command": None
	}

	def OnLoad(self, args, message):
		self.djAuths = {}

		if 'djs' in self.nv:
			for n in self.nv['djs'].split('::'):
				if n:
					self.djAuths[n] = self.DJDICT.copy()

		return True

	def OnModCommand(self, command):
		try:
			cmd = command.strip()

			if re.match('add(djs?)?', cmd, re.I):
				self.addDJ(cmd)
			elif re.match('del(djs?)?', cmd, re.I):
				self.delDJ(cmd)
			elif re.match('get(djs?)?', cmd, re.I):
				self.getDJs()
		except Exception as err:
			self.PutModule("OnModCommand Exception: " + str(err))

	# Check if the nick for an event is one we are keeping track of
	def OnPrivTextMessage(self, message):
		try:
			nick = message.GetNick().GetNick().lower()
			msgTxt = message.GetText()

			if nick in self.djAuths:
				self.checkForCommand(nick, msgTxt)
		except Exception as err:
			self.PutModule("OnPrivTextMessage Exception: " + str(err))
		
		return znc.CONTINUE

	# Check if the user tried to execute a command
	def checkForCommand(self, nick, message):
		self.PutModule("Checking for command for " + nick)

		try:
			match = re.match('[.!-](kill|dj|thread|auth|help|deauth)', message, re.I)

			if match:
				if not self.djAuths[nick]["authed"]:
					self.djAuths[nick]["command"] = message
					self.attemptAuth(nick)
					return
				
				cmd = match.group(1).lower()

				if cmd == "help":
					self.showHelp(nick)
				elif cmd == "kill":
					self.killHanyuu(nick)
				elif cmd == "dj":
					self.setDJ(nick, message)
				elif cmd == "thread":
					self.setThread(nick, message)
				elif cmd == "deauth":
					self.sendMessage(nick, "De-authorizing")
					self.deauthNick(nick)
		except Exception as err:
			self.PutModule("checkForCommand Exception: " + str(err))
	
	def getDJs(self):
		if len(self.djAuths) > 0:
			djStr = ""
			for n in self.djAuths:
				djStr += n + ", "
			
			djStr = djStr.strip(" ,")
			self.PutModule("Current DJs: {0}".format(djStr))
		else:
			self.PutModule("No explicit admins.")

	def addDJ(self, cmd):
		match = re.match(r'add(?:djs?)?\s+([\S\s]+)', cmd, re.I)

		if match:
			nicks = match.group(1).split(" ")
			nstr = ""
			for n in nicks:
				lc = n.lower()
				if lc and lc not in self.djAuths:
					self.djAuths[lc] = self.DJDICT.copy()
					nstr += n + ", "
			
			djStr = ""
			for n in self.djAuths:
				djStr += n + "::"

			nstr = nstr.strip(" ,")
			self.nv['djs'] = djStr.strip("::")
			self.PutModule("Added {0} to the DJ list".format(nstr))

	def delDJ(self, cmd):
		match = re.match(r'del(?:djs?)?\s+([\S\s]+)', cmd, re.I)

		if match:
			nicks = match.group(1).split(" ")
			nstr = ""
			for n in nicks:
				lc = n.lower()
				if lc and lc in self.djAuths:
					del self.djAuths[lc]
					nstr += n + ", "
			
			djStr = ""
			for n in self.djAuths:
				djStr += n + "::"

			nstr = nstr.strip(" ,")
			self.nv['djs'] = djStr.strip("::")
			self.PutModule("Removed {0} from the DJ list".format(nstr))

	# Authorize a nick for at most 24 hours
	def authNick(self, nick):
		self.PutModule("Attempting auth for " + nick)

		try:
			nick = nick.lower()

			if nick in self.djAuths:
				self.deauthNick(nick)
				self.djAuths[nick]["authed"] = True

				timer = self.CreateTimer(auth_timer, interval=(60 * 60 * 24), label=nick)
				timer.nick = nick
				self.djAuths[nick]["timeout"] = timer
				self.sendMessage(nick, "You are now authed for the next 24 hours, or until you part from #r/a/dio or disconnect from IRC")
				
				if self.inRadio():
					self.sendMessage(self.RADIO, "{0} has taken control".format(nick))

				if self.djAuths[nick]["command"]:
					self.checkForCommand(nick, self.djAuths[nick]["command"])
					self.djAuths[nick]["command"] = None
				
				self.PutModule(nick + " successfully authed")
		except Exception as err:
			self.PutModule("authNick Exception: " + str(err))

	# De-authorize a nick
	def deauthNick(self, nick):
		try:
			nick = nick.lower()

			if nick in self.djAuths:
				timer = self.djAuths[nick]["timeout"]
				if timer:
					timer.Stop()
				
				self.djAuths[nick]["authed"] = False
				self.djAuths[nick]["timeout"] = None
		except Exception as err:
			self.PutModule("deauthNick Exception: " + str(err))

	# Kill Hanyuu ;_;
	def killHanyuu(self, nick):
		self.PutModule("Killing Hanyuu for " + nick)

		try:
			self.sendIfInRadio(".kill", nick)
		except Exception as err:
			self.PutModule("killHanyuu Exception: " + str(err))

	# .dj proxy command. Sets DJ to user executing command if no arguments given
	def setDJ(self, nick, message):
		self.PutModule("SetDJ triggered")

		try:
			djName = nick
			match = re.match(r'[.!-]dj\s*(.+)', message, re.I)

			if match:
				djName = match.group(1)

			self.sendIfInRadio(".dj " + djName, nick)
			self.PutModule("Set DJ to " + djName)
		except Exception as err:
			self.PutModule("setDJ Exception: " + str(err))

	# .thread proxy command. Sets thread to None of no arguments given
	def setThread(self, nick, message):
		self.PutModule("SetThread triggered")

		try:
			threadMatch = re.match(r'[.!-]thread\s*(\S+)', message, re.I)
			thread = "none"

			if threadMatch:
				thread = threadMatch.group(1)

			self.sendIfInRadio(".thread " + thread, nick)
			self.PutModule("Set thread to " + thread)
		except Exception as err:
			self.PutModule("setThread Exception: " + str(err))

	# Display help for user
	def showHelp(self, nick):
		self.PutModule("Showing help for " + nick)

		try:
			self.sendMessage(nick, "PM me .auth to attempt authorization (not needed). When authed, you can PM me .kill, .dj, and .thread commands just like you would in the channel, as well as .deauth for early de-auth.")
			self.sendMessage(nick, ".dj without arguments will set yourself as DJ, else it will set what you give it as DJ.")
			self.sendMessage(nick, ".thread without arguments will set the thread to none, else it will set what you give it.")
		except Exception as err:
			self.PutModule("showHelp Exception: " + str(err))

	# Attempt authorization by checking NickServ status of user
	def attemptAuth(self, nick):
		self.PutModule("Attempting auth for " + nick)

		try:
			self.sendMessage(self.NICKSERV, "status " + nick)
		except Exception as err:
			self.PutModule("attemptAuth Exception: " + str(err))

	# Callback for the NickServ status (which is received as a notice). We are looking for status 3, which means they are identified by logging into NickServ
	def OnPrivNoticeMessage(self, message):
		try:
			ntcnick = (message.GetNick().GetNick()).lower()
			msg = message.GetText()

			if ntcnick == self.NICKSERV:
				match = re.match(r"status (\S+) (\d)", msg, re.I)

				if match:
					nick = match.group(1)
					status = match.group(2)
					if not nick in self.djAuths:
						return

					if status == "3":
						self.authNick(nick)
					else:
						self.sendMessage(nick, "Auth failed. NickServ status returned " + status + ", expected 3. Please make sure you have identified with NickServ.")
		except Exception as err:
			self.PutModule("OnPrivNoticeMessage Exception: " + str(err))
		
		return znc.CONTINUE

	# Quit handler. Auto de-auth if user quits from IRC
	def OnQuitMessage(self, message, chans):
		try:
			nick = message.GetNick().GetNick().lower()

			if nick in self.djAuths and self.djAuths[nick]["authed"]:
				self.deauthNick(nick)
		except Exception as err:
			self.PutModule("OnPartMessage Exception: " + str(err))

		return znc.CONTINUE

	# Part handler, same as quit handler
	def OnPartMessage(self, message):
		try:
			nick = message.GetNick().GetNick().lower()
			chan = message.GetChan().GetName().lower()

			if nick in self.djAuths and chan == self.RADIO:
				self.deauthNick(nick)
		except Exception as err:
			self.PutModule("OnPartMessage Exception: " + str(err))

		return znc.CONTINUE
	
	# Check if we are in #r/a/dio
	def inRadio(self) -> bool:
		try:
			radioChan = self.GetNetwork().FindChan(self.RADIO)

			if radioChan:
				return True
			else:
				return False
		except Exception as err:
			self.PutModule("inRadio Exception: " + str(err))

	# Verify we are in #r/a/dio before sending a command
	def sendIfInRadio(self, message, nick):
		try:
			if self.inRadio():
				self.sendMessage(self.RADIO, message)
			else:
				self.sendMessage(nick, "I do not seem to be in #r/a/dio. Unable to send command.")
		except Exception as err:
			self.PutModule("sendIfInRadio Exception: " + str(err))
	
	# Send a message to IRC, as well as the connected clients to ensure it shows up
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
