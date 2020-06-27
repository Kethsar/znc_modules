'''
	This script allows r/a/dio staff to give temporary, restricted access to
	a user so that they may guest DJ. The access expires after 24 hours,
	when they disconnect, or leave the channel. 
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
		self.GetModule().deauth(self.nick)

class hanyuu_guestauth_znc(znc.Module):
	description = "Authorize someone to use Hanyuu in #r/a/dio"

	RADIO = "#r/a/dio"
	AUTHDICT = {
		"killed": False,
		"threads": 0,
		"thread": "",
		"timer": None,
		"nick": ""
	}
	blacklist = []
	admins = []
	authObj = {}

	def OnLoad(self, args, message):
		if not 'pass' in self.nv:
			self.PutModule("Password is missing, please set one using setpass")

		if not 'help' in self.nv:
			self.PutModule("Help URL is missing, please set one using sethelp")

		if not 'server' in self.nv:
			self.PutModule("Server URL is missing, please set one using setserver")

		if 'blacklist' in self.nv:
			for n in self.nv['blacklist'].split('::'):
				if n:
					self.blacklist.append(n)

		if 'admins' in self.nv:
			for n in self.nv['admins'].split('::'):
				if n:
					self.admins.append(n)

		return True

	def OnModCommand(self, command):
		try:
			cmd = command.strip()

			if re.match('list(guests?)?', cmd, re.I):
				self.listGuests()
			elif re.match('setpass', cmd, re.I):
				self.setPass(cmd)
			elif re.match('getpass', cmd, re.I):
				self.getPass()
			elif re.match('getbl(acklist)?', cmd, re.I):
				self.getBlacklist()
			elif re.match('getadmins', cmd, re.I):
				self.getAdmins()
			elif re.match('addadmin', cmd, re.I):
				self.addAdmin(cmd)
			elif re.match('deladmin', cmd, re.I):
				self.delAdmin(cmd)
			elif re.match('sethelp', cmd, re.I):
				self.setHelp(cmd)
			elif re.match('gethelp', cmd, re.I):
				self.getHelp()
			elif re.match('setserver', cmd, re.I):
				self.setServer(cmd)
			elif re.match('getserver', cmd, re.I):
				self.getServer()
			else:
				self.checkForAdminCommand(cmd)
		except Exception as err:
			self.PutModule("OnModCommand Exception: " + str(err))
		
	def OnPrivTextMessage(self, message):
		try:
			nick = message.GetNick().GetNick().lower()
			msgTxt = message.GetText()

			if nick in self.authObj:
				self.checkForUserCommand(msgTxt, nick)
		except Exception as err:
			self.PutModule("OnPrivTextMessage Exception: " + str(err))
		
		return znc.CONTINUE

	def OnChanTextMessage(self, message):
		try:
			chan = str(message.GetChan())
			zncnick = message.GetNick()

			if chan.lower() == "#r/a/dio" and self.isAdmin(zncnick):
				msgTxt = message.GetText()
				match = re.match("[.!-]", msgTxt)

				if match:
					msgTxt = re.sub("[.!-]", "", msgTxt).strip()
					self.checkForAdminCommand(msgTxt, True)

			
		except Exception as err:
			self.PutModule("OnChanTextMessage Exception: " + str(err))
		
		return znc.CONTINUE
	
	def OnPartMessage(self, message):
		try:
			nick = message.GetNick().GetNick().lower()
			self.deauth(nick)
		except Exception as err:
			self.PutModule("OnPartMessage Exception: " + str(err))
	
	def OnQuitMessage(self, message, vchans):
		try:
			nick = message.GetNick().GetNick().lower()
			self.deauth(nick)
		except Exception as err:
			self.PutModule("OnQuitMessage Exception: " + str(err))

	def checkForAdminCommand(self, cmd, fromChan = False):
		if re.match('guestauth|guest|auth', cmd, re.I):
			self.setAuth(cmd, fromChan)
		elif re.match('resetauth', cmd, re.I):
			self.resetAuth()
		elif re.match('blacklist(guest)?', cmd, re.I):
			self.blacklistNick(cmd)
		elif re.match('whitelist(guest)?', cmd, re.I):
			self.whitelistNick(cmd)

	def setPass(self, cmd):
		match = re.match(r'setpass (\S+)', cmd, re.I)

		if match:
			password = match.group(1)
			self.nv['pass'] = password
			self.PutModule("Password set to {0}".format(password))
	
	def getPass(self):
		if 'pass' in self.nv:
			self.PutModule("Current password: {0}".format(self.nv['pass']))
		else:
			self.PutModule("Password not set.")

	def setHelp(self, cmd):
		match = re.match(r'sethelp (\S+)', cmd, re.I)

		if match:
			helpurl = match.group(1)
			self.nv['help'] = helpurl
			self.PutModule("Help URL set to {0}".format(helpurl))
	
	def getHelp(self):
		if 'help' in self.nv:
			self.PutModule("Current Help URL: {0}".format(self.nv['help']))
		else:
			self.PutModule("Help URL not set.")

	def setServer(self, cmd):
		match = re.match(r'setserver (\S+)', cmd, re.I)

		if match:
			server = match.group(1)
			self.nv['server'] = server
			self.PutModule("Server Address set to {0}".format(server))
	
	def getServer(self):
		if 'server' in self.nv:
			self.PutModule("Current Server Address: {0}".format(self.nv['server']))
		else:
			self.PutModule("Server Address not set.")
	
	def getAdmins(self):
		if len(self.admins) > 0:
			adminStr = ""
			for n in self.admins:
				adminStr += n + ", "
			
			adminStr = adminStr.strip(" ,")
			self.PutModule("Current admins: {0}".format(adminStr))
		else:
			self.PutModule("No explicit admins.")

	def addAdmin(self, cmd):
		match = re.match(r'addadmin\s+(\S+)', cmd, re.I)

		if match:
			nick = match.group(1)
			lc = nick.lower()
			if lc not in self.admins:
				self.admins.append(lc)

				adminStr = ""
				for n in self.admins:
					adminStr += n + "::"
				
				self.nv['admins'] = adminStr.strip("::")
				self.PutModule("Added {0} as admin".format(nick))

	def delAdmin(self, cmd):
		match = re.match(r'deladmin\s+(\S+)', cmd, re.I)

		if match:
			nick = match.group(1)
			lc = nick.lower()
			if lc in self.admins:
				self.admins.remove(lc)

				adminStr = ""
				for n in self.admins:
					adminStr += n + "::"
				
				self.nv['admins'] = adminStr.strip("::")
				self.PutModule("Removed {0} as admin".format(nick))
	
	def getBlacklist(self):
		if len(self.blacklist) > 0:
			blstr = ""
			for n in self.blacklist:
				blstr += n + ", "

			blstr = blstr.strip(" ,")
			self.PutModule("Current blacklisted nicks: {0}".format(blstr))
		else:
			self.PutModule("No blacklisted nicks.")

	def blacklistNick(self, cmd):
		match = re.match(r'blacklist(?:guest)?\s+([\S\s]+)', cmd, re.I)

		if match:
			nicks = match.group(1).split(" ")
			nstr = ""
			for n in nicks:
				lc = n.lower()
				if lc and lc not in self.blacklist:
					self.blacklist.append(lc)
					nstr += n + ", "
			
			blstr = ""
			for n in self.blacklist:
				blstr += n + "::"

			nstr = nstr.strip(" ,")
			self.nv['blacklist'] = blstr.strip("::")
			self.PutModule("Added {0} to the blacklist".format(nstr))

	def whitelistNick(self, cmd):
		match = re.match(r'whitelist(?:guest)?\s+([\S\s]+)', cmd, re.I)

		if match:
			nicks = match.group(1).split(" ")
			nstr = ""
			for n in nicks:
				lc = n.lower()
				if lc and lc in self.blacklist:
					self.blacklist.remove(lc)
					nstr += n + ", "
			
			blstr = ""
			for n in self.blacklist:
				blstr += n + "::"

			nstr = nstr.strip(" ,")
			self.nv['blacklist'] = blstr.strip("::")
			self.PutModule("Removed {0} from the blacklist".format(nstr))

	def setAuth(self, cmd, fromChan = False):
		match = re.match(r'(?:guestauth|guest|auth)\s+([\S\s]+)', cmd, re.I)

		if match:
			nicks = match.group(1).split(" ")
			nstr = ""
			blstr = ""

			for n in nicks:
				if n:
					if n.lower() not in self.blacklist:
						nstr += n + ", "
						self.setAllowedNick(n)
					else:
						blstr += n + ", "
			
			nstr = nstr.strip(' ,')
			blstr = blstr.strip(' ,')
			self.sendMessage(self.RADIO, "{0} is/are authorized to guest DJ. Stick around for a comfy fire.".format(nstr))

			if fromChan and len(blstr) > 0:
				self.sendMessage(self.RADIO, "{0} is/are blacklisted and not authorized to guest DJ.".format(blstr))
		else:
			self.PutModule("Provide a nick that will be allowed to set Hanyuu as DJ")

	def setAllowedNick(self, nick):
		lnick = nick.lower()
		if lnick in self.authObj:
			self.deauth(lnick)
		
		self.authObj[lnick] = self.AUTHDICT.copy()
		self.authObj[lnick]["timer"] = self.CreateTimer(auth_timer, interval=(60 * 60 * 24))
		self.authObj[lnick]["timer"].nick = nick
		self.authObj[lnick]["nick"] = nick
		self.PutModule('{0} can use Hanyuu within the next 24 hours'.format(nick))
		self.sendMessage(nick, "You have been authorized to use Hanyuu within the next 24 hours. PM me .help for information.")
		self.sendMessage(nick, "The password changes regularly. If you are a veteran guest streamer and just need the password, PM me .getpass to avoid the full help message.")

	def checkForUserCommand(self, cmd, nick):
		if re.match('[.!-]kill', cmd, re.I):
			self.killHanyuu(nick)
		elif re.match('[.!-]dj', cmd, re.I):
			self.setDJ(nick, cmd)
		elif re.match('[.!-]thread', cmd, re.I):
			self.setThread(nick, cmd)
		elif re.match('[.!-]guests', cmd, re.I):
			self.showGuests(nick)
		elif re.match('[.!-]help', cmd, re.I):
			self.showHelp(nick)
		elif re.match('[.!-]setname', cmd, re.I):
			self.setName(nick, cmd)
		elif re.match('[.!-]getname', cmd, re.I):
			self.showName(nick)
		elif re.match('[.!-]getpass', cmd, re.I):
			self.showPass(nick)

	def killHanyuu(self, nick):
		if self.authObj[nick]["killed"]:
			self.sendMessage(nick, "You have already used your kill privilege. Ask me to reset it if you fucked up.")
		elif not re.search('hanyuu', self.getCurrentDJ(), re.I):
			self.sendMessage(nick, "Hanyuu is not the DJ, so there is no need to kill her. Murderer.")
		else:
			self.sendIfInRadio(".kill", nick)
			self.sendIfInRadio(".thread none", nick)
			self.sendMessage(nick, "Hanyuu has been killed. Don't forget to connect around 30 seconds left in the song, and to set yourself as DJ with .dj")

	def setDJ(self, nick, cmd):
		if self.isDJ(nick):
			self.authObj[nick]["killed"] = True
			djmatch = re.match(r'[.!-]dj\s*(\S+)\s*', cmd, re.I)
			
			if djmatch:
				djn = djmatch.group(1).lower()
				if djn.startswith('hanyuu'):
					self.sendIfInRadio(".dj Hanyuu-sama", nick)
					return

				if not djn in self.authObj or self.authObj[djn]["killed"]:
					self.sendMessage(nick, "That user is not authorized to guest DJ")
					return
				
				self.setDJ(djn, None)
			else:
				self.sendMessage(nick, "You are already set as DJ")
		elif self.authObj[nick]["killed"]:
			self.sendMessage(nick, "You have already been set as DJ once before. Ask in the channel for help if you fucked up.")
		else:
			self.sendIfInRadio(".dj guest:" + self.authObj[nick]["nick"], nick)
			self.authObj[nick]["killed"] = True
			self.sendMessage(nick, "Don't foget to '.dj <something>' in the channel or PM me '.dj hanyuu' when you are done to give Hanyuu control again.")
			self.sendMessage(nick, "Alternatively you can set any of the other guests available using '.dj <guestname>' here (NOT IN THE CHANNEL). Type .guests to see who there is.")

	def showGuests(self, nick):
		nstr = ""
		for k in self.authObj.keys():
			if not self.authObj[k]["killed"]:
				nstr += k + ", "
		
		if nstr:
			nstr = "Available guests: " + nstr.strip(' ,')
		else:
			nstr = "No other guests available to be set as DJ"
		
		self.sendMessage(nick, nstr)

	def listGuests(self):
		gstr = ""
		for k in self.authObj.keys():
			gstr += self.authObj[k]["nick"] + ", "
		
		if gstr:
			gstr = "Authed guests: " + gstr.strip(' ,')
		else:
			gstr = "No are currently authed"
		
		self.PutModule(gstr)

	def setThread(self, nick, cmd):
		if self.isDJ(nick):
			threadMatch = re.match(r'[.!-]thread\s*(\S+)\s*', cmd, re.I)

			if threadMatch:
				thread = threadMatch.group(1)

				if self.authObj[nick]["threads"] >= 3:
					self.sendMessage(nick, "You've set enough threads. Ask a someone in the channel to help you out.")
				elif thread != self.authObj[nick]["thread"]:
					self.sendIfInRadio(".thread " + thread, nick)
					self.authObj[nick]["thread"] = thread
					self.authObj[nick]["threads"] += 1
				else:
					self.sendMessage(nick, "That is the current thread!")
			else:
				self.sendIfInRadio(".thread none", nick)
		else:
			self.sendMessage(nick, "You should set yourself as DJ first with .dj")

	def getGuestPass(self):
		password = "<password not set, tell Kethsar he is retarded>"
		if 'pass' in self.nv:
			password = self.nv['pass']

		return password

	def showHelp(self, nick):
		if not 'server' in self.nv:
			self.sendMessage(nick, "It seems the server has not been set. Tell Kethsar to get his shit together.")
			return

		password = self.getGuestPass()
		server = self.nv['server']

		self.sendMessage(nick, "Connection Info: Address: {0}, mount: main (for loopstream) or main.mp3 (for most everything else), user: guest, pass: {1}".format(server, password))
		self.sendMessage(nick, "If you are on linux and using SHIT, the connection info goes in the config's <url> tag as http://{0}/main.mp3".format(server))
		self.sendMessage(nick, "Please do a test connection before streaming if you have not streamed recently. This means connecting WITHOUT killing Hanyuu to make sure you can connect. Music will not go through, don't worry. Disconnect when you feel its okay.")
		self.sendMessage(nick, "When you are finished streaming, PM me '.dj hanyuu', OR type '.dj <whatever>' !!! IN #r/a/dio !!!(<- important) to set Hanyuu as DJ. <whatever> can be literally anything, like dongs, but CANNOT be blank.")

		if 'help' in self.nv:
			self.sendMessage(nick, "Commands and other information (recent-ish updates noted on page): {0}".format(self.nv['help']))

	def setName(self, nick, cmd):
		nameMatch = re.match(r'[.!-]setname\s*(.{1,20})', cmd, re.I)

		if nameMatch:
			name = nameMatch.group(1)
			self.authObj[nick]["nick"] = name
			self.showName(nick)

	def showName(self, nick):
		self.sendMessage(nick, "Your DJ name will be set as {0} when you DJ yourself".format(self.authObj[nick]["nick"]))

	def showPass(self, nick):
		password = self.getGuestPass()
		self.sendMessage(nick, "The current password is {0}".format(password))

	def resetAuth(self, timer=None):
		akeys = list(self.authObj.keys())
		
		for k in akeys:
			self.deauth(k)

	def deauth(self, nick):
		if nick in self.authObj:
			if self.authObj[nick]["timer"]:
				self.authObj[nick]["timer"].Stop()

			del self.authObj[nick]
			self.PutModule("{0} de-authed".format(nick))

	def getCurrentDJ(self):
		curDJ = ''
		self.PutModule("Checking current DJ")

		if self.inRadio():
			topic = self.GetNetwork().FindChan(self.RADIO).GetTopic()
			topic = re.sub("\x03([0-9]{1,2}(,[0-9]{1,2})?)?", "", topic)
			match = re.search(r'DJ:\s+(\S+)\s+https://r-a-d.io', topic, re.I)

			if match:
				curDJ = match.group(1)
		
		return curDJ

	def isDJ(self, nick):
		return re.search('guest:' + self.authObj[nick]["nick"], self.getCurrentDJ(), re.I)
	
	# Check if we are in #r/a/dio
	def inRadio(self):
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

	def hasAccess(self, zncnick):
		return (self.isAdmin(zncnick) or
				zncnick.HasPerm("%"))

	def isAdmin(self, zncnick):
		return (zncnick.HasPerm("@") or 
				zncnick.HasPerm("&") or
				zncnick.HasPerm("~") or
				zncnick.GetNick().lower() in self.admins)
