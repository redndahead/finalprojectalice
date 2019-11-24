import json
import pycronofy
from datetime import datetime

from core.base.model.Module import Module
from core.dialog.model.DialogSession import DialogSession
from core.util.Decorators import IntentHandler


class FinalProjectAlice(Module):
	"""
	Author: Redndahead
	Description: Takes care of final project
	"""

	def __init__(self):
		self._SUPPORTED_INTENTS	= [
		]

		super().__init__(self._SUPPORTED_INTENTS)


	def onMessage(self, intent: str, session: DialogSession):

		sessionId = session.sessionId
		siteId = session.siteId
		slots = session.slots

	def onBooted(self):
		self.loadCalendar()

	def loadCalendar(self):
		key = self.getConfig('cronofykey')
		self.logInfo(f'key: {key}')
		calendarID = self.getConfig('calendarID')
		self.logInfo(f'calendarID: {calendarID}')
		cronofy = pycronofy.Client(access_token=key)

		from_date = '2019-11-22'
		to_date = '2019-11-24'
		timezone_id = 'US/Pacific'

		all_events = cronofy.read_events(calendar_ids=(calendarID,),
										 from_date=from_date,
										 to_date=to_date,
										 tzid=timezone_id,
										 localized_times=True
										 ).all()

		self.updateConfig(key="eventList", value=json.dumps(all_events))

	def randomlySpeak(self, init: bool = False):
		rnd = self.getConfig('refreshTime')
		#self.ThreadManager.doLater(interval=rnd, func=self.randomlySpeak)
		#self.logInfo(f'Scheduled next random speaking in {rnd} seconds')

		key = self.getConfig('cronofykey')
		self.logInfo(f'key: {key}')
		calendarID = self.getConfig('calendarID')
		self.logInfo(f'calendarID: {calendarID}')
		cronofy = pycronofy.Client(access_token=key)

		from_date = '2019-11-22'
		to_date = '2019-11-24'
		timezone_id = 'US/Pacific'

		#all_events = cronofy.read_events(calendar_ids=(calendarID,),
		#								 from_date=from_date,
		#								 to_date=to_date,
		#								 tzid=timezone_id
		#								 ).all()

		#eventsOutput = json.dumps(all_events)
		#self.logInfo(f'Calendar: {eventsOutput}')

		#for event in all_events:
		#	self.logInfo(f'{event["summary"]}')
		#	self.say(f'Event name: {event["summary"]}. Event Start: {event["start"]}')

	def formatTimeToVoice(self, time=''):
		date = datetime.strptime(time, "%Y-%m-%dT%H:%M:%S%z")

		time = str(date.hour)
		if date.hour == 0:
			time = "12"
		elif date.hour > 12:
			time = str(date.hour - 12)

		ampm = "a m"
		if date.hour >= 12:
			ampm = "p m"

		if date.minute > 0:
			time = time + ' ' + str(date.minute)

		time = time + ' ' + ampm
		return time

	@IntentHandler('NextMeeting')
	def nextMeeting(self, session: DialogSession, **_kwargs):
		eventList = json.loads(self.getConfig('eventList'))
		eventOutput = json.dumps(eventList[1])
		self.logInfo(f'event2: {eventOutput}')

		event = eventList[1]
		time = self.formatTimeToVoice(time=eventList[1]["start"]["time"])
		self.logInfo(f'time2: {time}')
		self.endDialog(session.sessionId, f'The next event is {event["summary"]}. It will begin at {time}')