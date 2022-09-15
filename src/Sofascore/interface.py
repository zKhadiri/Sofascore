# -*- coding: UTF-8 -*-
from Screens.Screen import Screen
from Components.ActionMap import ActionMap
from Components.Sources.List import List
from Components.MenuList import MenuList
from Components.Label import Label
from Tools.LoadPixmap import LoadPixmap
from Tools.Directories import resolveFilename , SCOPE_PLUGINS , fileExists
from Tools.BoundFunction import boundFunction
from Components.MultiContent import MultiContentEntryText, MultiContentEntryPixmap, MultiContentEntryPixmapAlphaTest, MultiContentEntryPixmapAlphaBlend, MultiContentTemplateColor
from enigma import gFont, eListboxPythonMultiContent, RT_HALIGN_LEFT, RT_HALIGN_CENTER, RT_WRAP, BT_HALIGN_CENTER ,BT_SCALE ,BT_KEEP_ASPECT_RATIO, eTimer
from twisted.web.client import downloadPage, getPage
from twisted.internet.ssl import ClientContextFactory
from twisted.internet._sslverify import ClientTLSOptions
from datetime import datetime, date
import json
try:
	from urllib.parse import urlparse
except ImportError:
	from urlparse import urlparse

def readFromFile(filename):
	_file = resolveFilename(SCOPE_PLUGINS, "Extensions/Sofascore/{}".format(filename))
	if fileExists(_file):
		with open(_file, 'r') as f:
			return f.read()


class WebClientContextFactory(ClientContextFactory):
	def __init__(self, url=None):
		domain = urlparse(url).netloc
		self.hostname = domain
	
	def getContext(self, hostname=None, port=None):
		ctx = ClientContextFactory.getContext(self)
		if self.hostname and ClientTLSOptions is not None: # workaround for TLS SNI
			ClientTLSOptions(self.hostname, ctx)
		return ctx


class SofaInterface(Screen):

	def __init__(self, session):
		Screen.__init__(self, session)
		self.session = session
		self.skin = readFromFile('assets/skin/SofaInterface.xml')
		self['sections'] = List()
		self['Sofaactions'] = ActionMap(['SofaAction'], {
			'cancel': self.exit,
			'ok': self.ok
		}, -1)
		self.sofaData = None
		self.onFirstExecBegin.append(boundFunction(self.getData, self.parseData))

	@classmethod
	def getData(self, callback):
		url = f'http://api.sofascore.com/api/v1/sport/football/scheduled-events/{date.today()}'
		getPage(str.encode(url), timeout=10, agent=b'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_6_8) AppleWebKit/537.13+ (KHTML, like Gecko) Version/5.1.7 Safari/534.57.2').addCallback(callback).addErrback(self.error, url)

	def parseData(self, data):
		if data:
			data = json.loads(data.decode('utf-8'))
			self.sofaData = data
			events = {'Live':{}}
			live_cpt = 1
			for event in self.sofaData['events']:
				event_name = event['tournament']['category']['name']
				if date.fromtimestamp(event['startTimestamp']) >= date.today():
					if not event_name in events:
						events[event_name] = {}
						if "alpha2" in event['tournament']['category']:
							events[event_name] = {"flag" : event['tournament']['category']["alpha2"].lower(), "count": 1}
						else:
							events[event_name] = {"flag" : event['tournament']['category']["slug"].lower(), "count": 1}
					else:
						events[event_name]['count'] += 1
					if event['status']['type'] == 'inprogress':
						events['Live'] = {"flag" : "live", "count": live_cpt}
						live_cpt += 1
			if len(events) > 0:
				self['sections'].setList([(k, v['flag'], None, str(v['count'])) for k, v in events.items()])
				for idx,flag in enumerate(self['sections'].list):
					self.downloadFlag(flag[1], idx)

	def downloadFlag(self, flag, idx):
		if fileExists(f'/tmp/{flag}.png'):
			self.setFlag(idx, f'/tmp/{flag}.png')
		else:
			url = f'https://www.sofascore.com/static/images/flags/{flag}.png'
			sniFactory = WebClientContextFactory(url)
			downloadPage(str.encode(url), f'/tmp/{flag}.png', contextFactory=sniFactory, timeout=10, agent=b'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_6_8) AppleWebKit/537.13+ (KHTML, like Gecko) Version/5.1.7 Safari/534.57.2').addCallback(self.downloadCallback, f'/tmp/{flag}.png', idx).addErrback(self.error, url)
	
	def downloadCallback(self, data, flag_path, idx):
		if fileExists(flag_path):
			self.setFlag(idx, flag_path)

	def setFlag(self, idx, flag_path):
		ptr = LoadPixmap(path=flag_path)
		if ptr:
			_list = self['sections'].list
			_list[idx] = (_list[idx][0], _list[idx][1], ptr, _list[idx][3])
			self['sections'].updateList(_list)

	@classmethod
	def sortDataBySection(cls, section, data):
		events = {}
		for event in data['events']:
			if section == 'Live':
				events['Live'] = []
				for event in data['events']:
					if event['status']['type'] == 'inprogress':
						events['Live'].append(event)
			else:
				event_name = event['tournament']['category']['name']
				if event_name == section and date.fromtimestamp(event['startTimestamp']) >= date.today():
					if event_name not in events:
						events[event_name] = []
						events[event_name].append(event)
					else:
						events[event_name].append(event)
		return events
	
	def error(self, error, url):
		if error:
			print(error, url)

	def ok(self):
		curr_section = self['sections'].getCurrent()[0]
		events = self.sortDataBySection(curr_section, self.sofaData)
		if len(events) > 0:
			self.session.open(SofaSections, curr_section, events)

	def exit(self):
		self.close()

class SofaSections(Screen):

	def __init__(self, session, section, events):
		Screen.__init__(self, session)
		self.session = session
		self.section = section
		self.events = events
		# self['title'] = Label()
		# self['title'].setText(section)
		self['tournaments'] = List()
		self.skin = readFromFile('assets/skin/SofaSections.xml')
		self['Sofaactions'] = ActionMap(['SofaAction'], {
			'cancel': self.exit,
			'ok': self.ok,
		}, -1)
		self.onLayoutFinish.append(self._onLayoutFinish)

	def _onLayoutFinish(self):
		tournaments = {}
		for event in self.events[self.section]:
			event_id = event['tournament']['uniqueTournament']['id']
			event_name = event['tournament']['uniqueTournament']['name']
			event_slug = event['tournament']['uniqueTournament']['slug']
			if event_slug not in tournaments:
				tournaments[event_slug] = {"id": event_id,"name": event_name, 'count': 1}
			else:
				tournaments[event_slug]['count'] += 1
		if len(tournaments) > 0:
			self['tournaments'].setList([(k, v['id'], v['name'], str(v['count']), None) for k, v in tournaments.items()])
			for idx,tournament in enumerate(self['tournaments'].list):
				self.downloadIcon(tournament[1], f'{tournament[0]}.png', idx)

	def downloadIcon(self, id, icon_name, idx):
		if fileExists(f'/tmp/{icon_name}'):
			self.setIcon(idx, f'/tmp/{icon_name}')
		else:
			url = f'http://api.sofascore.app/api/v1/unique-tournament/{id}/image'
			downloadPage(str.encode(url), f'/tmp/{icon_name}', timeout=10, agent=b'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_6_8) AppleWebKit/537.13+ (KHTML, like Gecko) Version/5.1.7 Safari/534.57.2').addCallback(self.downloadCallback, f'/tmp/{icon_name}', idx).addErrback(self.error, url)

	def downloadCallback(self, data, flag_path, idx):
		if fileExists(flag_path):
			self.setIcon(idx, flag_path)

	def setIcon(self, idx, flag_path):
		ptr = LoadPixmap(path=flag_path)
		if ptr:
			_list = self['tournaments'].list
			_list[idx] = (_list[idx][0], _list[idx][1], _list[idx][2], _list[idx][3], ptr)
			self['tournaments'].updateList(_list)
	
	def error(self, error, url):
		if error:
			print(error, url)

	def ok(self):
		curr_tournament = self['tournaments'].getCurrent()[0]
		total_events = self['tournaments'].getCurrent()[3]
		self.session.open(SofaEvents, self.section, self.events, curr_tournament, total_events)

	def exit(self):
		self.close()

class SofaEvents(Screen):

	def __init__(self, session, section, events, curr_tournament, total_events):
		Screen.__init__(self, session)
		self.session = session
		self.section = section
		self.events = events
		self.curr_tournament = curr_tournament
		self.total_events = total_events
		self['title'] = Label()
		self['title'].setText(section)
		self['events'] = MenuList([], enableWrapAround=True, content=eListboxPythonMultiContent)
		self['events'].l.setBuildFunc(self.buildEntry)
		self["events"].l.setFont(0, gFont('Bold', 26))
		self["events"].l.setFont(1, gFont('Regular', 24))
		self.skin = readFromFile('assets/skin/SofaEvents.xml')
		self['Sofaactions'] = ActionMap(['SofaAction'], {
			'cancel': self.exit,
			'ok': self.ok,
		}, -1)
		self.timer = eTimer()
		self.timer.callback.append(self.updateData)
		self.onLayoutFinish.append(self._onLayoutFinish)

	def _onLayoutFinish(self):
		self.fillList()
		self.timer.start(20000) #60000 1m

	def fillList(self):
		cpt = 1
		_list = []
		for event in sorted(self.events[self.section], key=lambda t: t['startTimestamp']):
			if self.curr_tournament == event['tournament']['uniqueTournament']['slug']: 
				score = ''
				#minutes_diff = int((datetime.now() - datetime.fromtimestamp(event['statusTime']['timestamp'])).total_seconds() // 60)
				if 'current' in event['homeScore'] and 'current' in event['awayScore']:
					score = f'{event["homeScore"]["current"]} - {event["awayScore"]["current"]}'
				startat = datetime.fromtimestamp(event['startTimestamp']).strftime('%H:%M %Y-%m-%d')
				_list.append((event['tournament']['name'], startat, event['homeTeam']['name'], event['awayTeam']['name'], score, f'{cpt}/{self.total_events}', event))
				cpt += 1
				# print(event['tournament']['uniqueTournament']['slug'])
		self['events'].setList(_list)

	def buildEntry(self, tournament_name, start_time, homeTeam, awayTeam, score, count, event):
		res = [None]
		# print(event['status'])
		forgroundColorResult = MultiContentTemplateColor("green")
		forgroundColorHome = MultiContentTemplateColor("white")
		forgroundColorAway = forgroundColorHome
		res.append(MultiContentEntryText(pos=(10,0),size=(1280,0),text="", backcolor=MultiContentTemplateColor("#00417a")))
		res.append(MultiContentEntryText(pos=(40,20),size=(980,32),text=tournament_name,flags=RT_HALIGN_LEFT, color=MultiContentTemplateColor("white"), color_sel=MultiContentTemplateColor("white"), backcolor_sel=MultiContentTemplateColor('#006ecc')))

		if event['status']['type'] == 'notstarted':
			res.append(MultiContentEntryText(pos=(70,75),size=(130,60),text=start_time,flags=RT_HALIGN_CENTER|RT_WRAP, color=MultiContentTemplateColor("white"),color_sel=MultiContentTemplateColor("white"), backcolor_sel=MultiContentTemplateColor('#006ecc')))
		if event['status']['type'] == 'finished':
			display_time = datetime.fromtimestamp(event['startTimestamp']).strftime('%H:%M')+'\nFT'
			res.append(MultiContentEntryText(pos=(70,75),size=(130,60),text=display_time,flags=RT_HALIGN_CENTER|RT_WRAP, color=MultiContentTemplateColor("#939596"),color_sel=MultiContentTemplateColor("#939596"), backcolor_sel=MultiContentTemplateColor('#006ecc')))
			if 'current' in event['homeScore'] and 'current' in event['awayScore']:
				if event['homeScore']["current"] > event['awayScore']["current"]:
					forgroundColorAway = MultiContentTemplateColor("#939596")
				if event['awayScore']["current"] > event['homeScore']["current"]:
					forgroundColorHome = MultiContentTemplateColor("#939596")
				if event['awayScore']["current"] == event['homeScore']["current"]:
					forgroundColorHome = MultiContentTemplateColor("#939596")
					forgroundColorAway = MultiContentTemplateColor("#939596")
			forgroundColorResult = MultiContentTemplateColor("white")
		if event['status']['type'] == 'inprogress':
			if event['status']['description'] == 'Halftime':
				display_time = datetime.fromtimestamp(event['startTimestamp']).strftime('%H:%M')+'\nHT'
				res.append(MultiContentEntryText(pos=(70,75),size=(130,60),text=display_time,flags=RT_HALIGN_CENTER|RT_WRAP, color=MultiContentTemplateColor("white"),color_sel=MultiContentTemplateColor("white"), backcolor_sel=MultiContentTemplateColor('#006ecc')))
			else:
				event_time = datetime.fromtimestamp(event['startTimestamp']).strftime('%H:%M')
				minutes_diff = int((datetime.now() - datetime.fromtimestamp(event['statusTime']['timestamp'])).total_seconds() // 60)
				minutes_diff += 45 if event['status']['description'] == '2nd half' else 0
				display_time = f"{event_time}\n{minutes_diff}'"
				res.append(MultiContentEntryText(pos=(70,75),size=(130,60),text=display_time,flags=RT_HALIGN_CENTER|RT_WRAP, color=MultiContentTemplateColor("white"), color_sel=MultiContentTemplateColor("white"), backcolor_sel=MultiContentTemplateColor('#006ecc')))
		if event['status']['type'] == 'canceled':
			res.append(MultiContentEntryText(pos=(70,75),size=(130,60),text="Canceled",flags=RT_HALIGN_CENTER|RT_WRAP, color=MultiContentTemplateColor("red"),color_sel=MultiContentTemplateColor("red"), backcolor_sel=MultiContentTemplateColor('#006ecc')))

		res.append(MultiContentEntryText(pos=(300,65),size=(450,30),text=homeTeam, color=forgroundColorHome, color_sel=forgroundColorHome, backcolor_sel=MultiContentTemplateColor('#006ecc')))
		res.append(MultiContentEntryText(pos=(300,110),size=(450,30),text=awayTeam, color=forgroundColorAway, color_sel=forgroundColorAway, backcolor_sel=MultiContentTemplateColor('#006ecc')))
		res.append(MultiContentEntryText(pos=(820,85),size=(70,30),text=score, color=forgroundColorResult, color_sel=forgroundColorResult, backcolor_sel=MultiContentTemplateColor('#006ecc')))
		res.append(MultiContentEntryText(pos=(1180,20),size=(100,30),text=count, font=1, color=MultiContentTemplateColor("#939596"), color_sel=MultiContentTemplateColor("#939596"), backcolor_sel=MultiContentTemplateColor('#006ecc')))
		return res

	def updateData(self):
		SofaInterface.getData(self.parseData)

	def parseData(self, data):
		if data:
			data = json.loads(data.decode('utf-8'))
			events = SofaInterface.sortDataBySection(self.section, data)
		if len(events) > 0:
			self.events = events
			# print("filled")
			self.fillList()

	def ok(self):
		self.timer.stop()
		curr_event = self['events'].getCurrent()[6]
		# print(curr_event['tournament']['uniqueTournament']['id'])
		self.session.open(SofaSingleEvent, curr_event)

	def exit(self):
		self.timer.stop()
		self.close()


class SofaSingleEvent(Screen):

	def __init__(self, session, event):
		Screen.__init__(self, session)
		self.session = session
		self.event = event
		self.skin = readFromFile('assets/skin/SofaSingleEvent.xml')
		self['homeTeamList'] = MenuList([], enableWrapAround=True, content=eListboxPythonMultiContent)
		self['homeTeamList'].l.setBuildFunc(self.buildEntry)
		self["homeTeamList"].l.setFont(0, gFont('Bold', 26))
		self["homeTeamList"].l.setFont(1, gFont('Regular', 24))
		self['Sofaactions'] = ActionMap(['SofaAction'], {
			'cancel': self.exit,
		}, -1)
		self.onFirstExecBegin.append(self.getData)

	def getData(self):
		url = f"https://api.sofascore.com/api/v1/team/{self.event['homeTeam']['id']}/events/last/0"
		sniFactory = WebClientContextFactory(url)
		getPage(str.encode(url), contextFactory=sniFactory, timeout=10, agent=b'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_6_8) AppleWebKit/537.13+ (KHTML, like Gecko) Version/5.1.7 Safari/534.57.2').addCallback(self.parseData).addErrback(self.error, url)

	def parseData(self, data):
		if data:
			data = json.loads(data.decode('utf-8'))
			_list = []
			for event in data['events']:
				# print(event['homeTeam']['name'], event['homeTeam']['id'], event['awayTeam']['name'], event['awayTeam']['id'])
				_list.append((event, ))
			self['homeTeamList'].setList(_list)

	def buildEntry(self, event):
		res = [None]
		forgroundColorHome = MultiContentTemplateColor("white")
		forgroundColorAway = MultiContentTemplateColor("white")
		res.append(MultiContentEntryText(pos=(0,0),size=(0,0),text="", backcolor=MultiContentTemplateColor("#00417a")))

		#homeTeam
		homeTeamLogo = event['homeTeam']['slug']+'.png'
		if fileExists(f'/tmp/{homeTeamLogo}'):
			ptr = LoadPixmap(path=f'/tmp/{homeTeamLogo}')
			if ptr:
				res.append(MultiContentEntryPixmapAlphaBlend(pos=(5,10),size=(120,120),png=ptr, flags=BT_SCALE|BT_KEEP_ASPECT_RATIO))
		else:
			teamId = event['homeTeam']['id']
			index = self['homeTeamList'].instance.getCurrentIndex()
			self.downloadLogo(homeTeamLogo, teamId, index)

		#awayTeam
		awayTeamLogo = event['awayTeam']['slug']+'.png'
		if fileExists(f'/tmp/{awayTeamLogo}'):
			ptr = LoadPixmap(path=f'/tmp/{awayTeamLogo}')
			if ptr:
				res.append(MultiContentEntryPixmapAlphaBlend(pos=(315,10),size=(120,120),png=ptr, flags=BT_SCALE|BT_KEEP_ASPECT_RATIO))
		else:
			teamId = event['awayTeam']['id']
			index = self['homeTeamList'].instance.getCurrentIndex()
			self.downloadLogo(awayTeamLogo, teamId, index)
		print(event['homeScore'], event['status'])
		return res

	def downloadLogo(self, logoName, logoId, idx):
		url = f'http://api.sofascore.app/api/v1/team/{logoId}/image'
		downloadPage(str.encode(url), f'/tmp/{logoName}', timeout=10, agent=b'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_6_8) AppleWebKit/537.13+ (KHTML, like Gecko) Version/5.1.7 Safari/534.57.2').addCallback(self.downloadCallback, idx).addErrback(self.error, url)

	def downloadCallback(self, data, idx):
		self['homeTeamList'].l.invalidateEntry(idx)

	def error(self, error, url):
		if error:
			print(error)

	def exit(self):
		self.close()