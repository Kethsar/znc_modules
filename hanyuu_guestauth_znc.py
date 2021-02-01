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
		"nick": "",
		"trykill": 0
	}
	blacklist = []
	admins = []
	authObj = {}

	# Set up some variables from persistent storage
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

	# Commands that can be used in the module query window
	# TODO: Possibly make this a jump-table or whatever to get rid of the evergrowing if tree
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
		
	# Check for guest commands when PMd
	def OnPrivTextMessage(self, message):
		try:
			nick = message.GetNick().GetNick().lower()
			msgTxt = message.GetText()

			if nick in self.authObj:
				self.checkForUserCommand(msgTxt, nick)
		except Exception as err:
			self.PutModule("OnPrivTextMessage Exception: " + str(err))
		
		return znc.CONTINUE

	# Check for admin commands in messages from #r/a/dio
	def OnChanTextMessage(self, message):
		try:
			chan = message.GetTarget()
			zncnick = message.GetNick()

			if chan.lower() == "#r/a/dio" and self.isAdmin(zncnick):
				msgTxt = message.GetText()
				match = re.match("[.!-]", msgTxt)

				if match:
					msgTxt = re.sub("^[.!-]", "", msgTxt).strip()
					self.checkForAdminCommand(msgTxt, True)
			
		except Exception as err:
			self.PutModule("OnChanTextMessage Exception: " + str(err))
		
		return znc.CONTINUE

	# Check for admin commands in messages to #r/a/dio from myself
	def OnUserTextMessage(self, message):
		try:
			chan = message.GetTarget()
			zncnick = message.GetNick()

			if chan.lower() == "#r/a/dio":
				msgTxt = message.GetText()
				match = re.match("[.!-]", msgTxt)

				if match:
					msgTxt = re.sub("^[.!-]", "", msgTxt).strip()
					self.checkForAdminCommand(msgTxt, True)
			
		except Exception as err:
			self.PutModule("OnChanTextMessage Exception: " + str(err))
		
		return znc.CONTINUE
	
	# De-auth guests if they part from #r/a/dio
	def OnPartMessage(self, message):
		try:
			nick = message.GetNick().GetNick().lower()
			self.deauth(nick)
		except Exception as err:
			self.PutModule("OnPartMessage Exception: " + str(err))
	
	# De-auth guests if they disconnect from the IRC server
	def OnQuitMessage(self, message, vchans):
		try:
			nick = message.GetNick().GetNick().lower()
			self.deauth(nick)
		except Exception as err:
			self.PutModule("OnQuitMessage Exception: " + str(err))

	# Commands that can be used by +o and higher in #r/a/dio, or by admins set manually
	# TODO: Possibly make a jump-table or something
	def checkForAdminCommand(self, cmd, fromChan = False):
		inChan = self.inRadio()
		if re.match('guesthelp', cmd, re.I):
			self.guestHelp(cmd)
		elif re.match('guestauth|guest|auth', cmd, re.I):
			if inChan:
				self.setAuth(cmd, fromChan)
			else:
				self.PutModNotice("Failed to auth user(s): You are not in #r/a/dio")
		elif re.match('resetauth', cmd, re.I):
			self.resetAuth()
		elif re.match('blacklist(guest)?', cmd, re.I):
			self.blacklistNick(cmd)
		elif re.match('whitelist(guest)?', cmd, re.I):
			self.whitelistNick(cmd)

	# Set the guest password
	def setPass(self, cmd):
		match = re.match(r'setpass (\S+)', cmd, re.I)

		if match:
			password = match.group(1)
			self.nv['pass'] = password
			self.PutModule("Password set to {0}".format(password))
	
	# Get the currently set guest password
	def getPass(self):
		if 'pass' in self.nv:
			self.PutModule("Current password: {0}".format(self.nv['pass']))
		else:
			self.PutModule("Password not set.")

	# Set the help page, shown on the last message sent when .help is triggered
	def setHelp(self, cmd):
		match = re.match(r'sethelp (\S+)', cmd, re.I)

		if match:
			helpurl = match.group(1)
			self.nv['help'] = helpurl
			self.PutModule("Help URL set to {0}".format(helpurl))
	
	# Get the currently set help page
	def getHelp(self):
		if 'help' in self.nv:
			self.PutModule("Current Help URL: {0}".format(self.nv['help']))
		else:
			self.PutModule("Help URL not set.")

	# Set the server URL that is meant to be streamed to, including port
	def setServer(self, cmd):
		match = re.match(r'setserver (\S+)', cmd, re.I)

		if match:
			server = match.group(1)
			self.nv['server'] = server
			self.PutModule("Server Address set to {0}".format(server))
	
	# Get the currently set server address
	def getServer(self):
		if 'server' in self.nv:
			self.PutModule("Current Server Address: {0}".format(self.nv['server']))
		else:
			self.PutModule("Server Address not set.")
	
	# Get the list of manually set admins that can trigger admin commands
	def getAdmins(self):
		if len(self.admins) > 0:
			adminStr = ""
			for n in self.admins:
				adminStr += n + ", "
			
			adminStr = adminStr.strip(" ,")
			self.PutModule("Current admins: {0}".format(adminStr))
		else:
			self.PutModule("No explicit admins.")

	# Add a user to the list of admins that can trigger admin commands
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

	# Remove a user from the list of admins
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
	
	# Get the list of users currently disallowed from streaming
	def getBlacklist(self):
		if len(self.blacklist) > 0:
			blstr = ""
			for n in self.blacklist:
				blstr += n + ", "

			blstr = blstr.strip(" ,")
			self.PutModule("Current blacklisted nicks: {0}".format(blstr))
		else:
			self.PutModule("No blacklisted nicks.")

	# Add a user to the blacklist to prevent them from being authorized as a guest
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

	# Remove a user from the blacklist and allow them to be authorized as a guest again
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

	# Attempt to authorize a user to guest stream
	def setAuth(self, cmd, fromChan = False):
		match = re.match(r'(?:guestauth|guest|auth)\s+([\S\s]+)', cmd, re.I)
		# We already check if we are in the channel before calling this function
		chanNicks = self.GetNetwork().FindChan(self.RADIO).GetNicks()
		lowerNicks = []

		for n in chanNicks:
			lowerNicks.append(n.lower())

		if match:
			nicks = match.group(1).split(" ")
			nstr = ""
			blstr = ""
			chstr = ""

			for n in nicks:
				if n:
					nl = n.lower()

					if nl in self.blacklist:
						blstr += n + ", "
					elif nl in lowerNicks:
						nstr += n + ", "
						self.setAllowedNick(n)
					else:
						chstr += n + ", "
			
			nstr = nstr.strip(' ,')
			blstr = blstr.strip(' ,')
			chstr = chstr.strip(' ,')

			if len(nstr) > 0:
				self.sendMessage(self.RADIO, "{0} is/are authorized to guest DJ. Stick around for a comfy fire.".format(nstr))

			if fromChan and len(blstr) > 0:
				self.sendMessage(self.RADIO, "{0} is/are blacklisted and not authorized to guest DJ.".format(blstr))
				
			if len(chstr) > 0:
				if fromChan:
					self.sendMessage(self.RADIO, "{0} is/are not in the channel and are ineligible for guest auth. Tell them to join the channel.".format(chstr))
				self.PutModNotice("{0} is/are not in the channel and are ineligible for guest auth".format(chstr))
		else:
			self.PutModule("Provide a nick that will be allowed to set Hanyuu as DJ")

	# Allows the given nick to use guest commands and stream. Resets the nick first if they are already authorized.
	def setAllowedNick(self, nick):
		lnick = nick.lower()
		if lnick in self.authObj:
			self.deauth(lnick)
		
		self.authObj[lnick] = self.AUTHDICT.copy()
		self.authObj[lnick]["timer"] = self.CreateTimer(auth_timer, interval=(60 * 60 * 24), label=nick)
		self.authObj[lnick]["timer"].nick = nick
		self.authObj[lnick]["nick"] = nick
		self.PutModule('{0} can use Hanyuu within the next 24 hours'.format(nick))
		self.sendMessage(nick, "You have been authorized to use Hanyuu within the next 24 hours. PM me .help for information.")
		self.sendMessage(nick, "The password changes regularly. If you are a veteran guest streamer and just need the password, PM me .getpass to avoid the full help message.")

	# Commands that can be used by guest DJs
	# TODO: Make this a jump-table or something
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

	# Kills Hanyuu ;_;
	# Sends the command to have Hanyuu disconnect after she finishes her current song
	def killHanyuu(self, nick):
		if self.authObj[nick]["killed"]:
			self.sendMessage(nick, "You have already used your kill privilege. Ask me to reset it if you fucked up.")
		elif not re.search('hanyuu', self.getCurrentDJ(), re.I):
			self.sendMessage(nick, "Hanyuu is not the DJ, so there is no need to kill her. Murderer.")
		elif self.authObj[nick]["trykill"] > 2: # implies "killed" is false since it was the first check
			self.sendMessage(nick, "You've made 3 attempts to kill Hanyuu and not become DJ. Are you too drunk for this? Let Kethsar or an admin know about this.")
		else:
			self.authObj[nick]["trykill"] += 1
			self.sendIfInRadio(".kill", nick)
			self.sendIfInRadio(".thread none", nick)
			self.sendMessage(nick, "Hanyuu has been killed. Don't forget to connect around 30 seconds left in the song, and to set yourself as DJ with .dj")

	# Set the user as DJ if they are not the currently set DJ
	# Can only be used by a guest once per authorization
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
			if re.search('hanyuu', self.getCurrentDJ(), re.I) and self.authObj[nick]["trykill"] < 1:
				self.sendMessage(nick, "You forgot to kill Hanyuu. I'll kill her for you, but it's usually better to kill her first and set yourself as DJ just before or after you start.")
				self.killHanyuu(nick)
			
			self.sendIfInRadio(".dj guest:" + self.authObj[nick]["nick"], nick)
			self.authObj[nick]["killed"] = True
			self.sendMessage(nick, "Don't foget to '.dj <something>' in the channel or PM me '.dj hanyuu' when you are done to give Hanyuu control again.")
			self.sendMessage(nick, "Alternatively you can set any of the other guests available using '.dj <guestname>' here (NOT IN THE CHANNEL). Type .guests to see who there is.")

	# Display a list of guests that can be set as DJ for the current guest
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

	# Display the currently authed guests
	def listGuests(self):
		gstr = ""
		for k in self.authObj.keys():
			gstr += self.authObj[k]["nick"] + ", "
		
		if gstr:
			gstr = "Authed guests: " + gstr.strip(' ,')
		else:
			gstr = "No users are currently authed"
		
		self.PutModule(gstr)

	# Set the given thread
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

	# Display the current guest password to the user
	def getGuestPass(self):
		password = "<password not set, tell Kethsar he is retarded>"
		if 'pass' in self.nv:
			password = self.nv['pass']

		return password

	# Show help message to a nick without having them authed
	def guestHelp(self, cmd):
		match = re.match(r'guesthelp\s+(\S+)', cmd, re.I)

		if match:
			nick = match.group(1)
			self.showHelp(nick)
			self.sendMessage(nick, "You are NOT actually authed yet. These messages were sent to aide with first-time setup.")

	# Send a set of help messages to the user
	def showHelp(self, nick):
		if not 'server' in self.nv:
			self.sendMessage(nick, "It seems the server has not been set. Tell Kethsar to get his shit together.")
			return

		password = self.getGuestPass()
		server = self.nv['server']

		self.sendMessage(nick, "Connection Info: Address: {0}, mount: main (for loopstream) or main.mp3 (for most everything else), user: guest, pass: {1}".format(server, password))
		#self.sendMessage(nick, "If you are on linux and using SHIT, the connection info goes in the config's <url> tag as http://{0}/main.mp3".format(server))
		self.sendMessage(nick, "Please do a test connection before streaming if you have not streamed recently. Do this by setting the mount to 'test' instead of 'main'. Be sure to set it back to 'main' when you are done testing.")
		self.sendMessage(nick, "When you are finished streaming, PM me '.dj hanyuu', OR type '.dj <whatever>' !!! IN #r/a/dio !!!(<- important) to set Hanyuu as DJ. <whatever> can be literally anything, like dongs, but CANNOT be blank.")

		if 'help' in self.nv:
			self.sendMessage(nick, "Commands and other information (recent-ish updates noted on page): {0}".format(self.nv['help']))

	# Set the DJ name a guest will be set to when they are set as DJ
	def setName(self, nick, cmd):
		nameMatch = re.match(r'[.!-]setname\s*(.{1,20})', cmd, re.I)

		if nameMatch:
			name = nameMatch.group(1)
			self.authObj[nick]["nick"] = name
			self.showName(nick)

	# Display the DJ name the user will be set as
	def showName(self, nick):
		self.sendMessage(nick, "Your DJ name will be set as {0} when you DJ yourself".format(self.authObj[nick]["nick"]))

	# Display the current guess password to the user
	def showPass(self, nick):
		password = self.getGuestPass()
		self.sendMessage(nick, "The current password is {0}".format(password))

	# Reset all guest authorizations
	def resetAuth(self):
		akeys = list(self.authObj.keys())
		
		for k in akeys:
			self.deauth(k)

	# De-auth the given user
	def deauth(self, nick):
		if nick in self.authObj:
			if self.authObj[nick]["timer"]:
				self.authObj[nick]["timer"].Stop()

			del self.authObj[nick]
			self.PutModule("{0} de-authed".format(nick))

	# Get the DJ currently set from the topic in #r/a/dio
	def getCurrentDJ(self):
		curDJ = ''
		self.PutModule("Checking current DJ")

		if self.inRadio():
			topic = self.GetNetwork().FindChan(self.RADIO).GetTopic()
			topic = re.sub("\x03([0-9]{1,2}(,[0-9]{1,2})?)?", "", topic)
			match = re.search(r'DJ:\s+(.+)\s{1,2}https://r-a-d.io', topic, re.I)

			if match:
				curDJ = match.group(1)
		
		return curDJ

	# Check if the given user is set as the DJ
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

	# Check if a user has +h or higher in a channel
	def hasAccess(self, zncnick):
		return (self.isAdmin(zncnick) or
				zncnick.HasPerm("%"))

	# Check if a user is +o or higherr in a channel, or is a manually set admin
	def isAdmin(self, zncnick):
		return (zncnick.HasPerm("@") or 
				zncnick.HasPerm("&") or
				zncnick.HasPerm("~") or
				zncnick.GetNick().lower() in self.admins)
