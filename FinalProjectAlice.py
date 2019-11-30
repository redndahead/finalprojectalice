import json
import pycronofy
from datetime import datetime, timedelta
import pytz

from core.base.model.Intent import Intent
from core.base.model.Module import Module
from core.dialog.model.DialogSession import DialogSession
from core.util.Decorators import IntentHandler


class FinalProjectAlice(Module):
	"""
	Author: Redndahead
	Description: Takes care of final project
	"""

	_INTENT_ATTENDEE_THERE = Intent('AttendeeThere')

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
		self.updateConfig(key="verification", value="")
		self.checkVerification()

	def loadCalendar(self):
		calendar_refresh_time = self.getConfig('calendarRefreshTime')
		self.ThreadManager.doLater(interval=calendar_refresh_time, func=self.loadCalendar)
		self.logInfo(f'Scheduled next calendar load in {calendar_refresh_time} seconds')

		key = self.getConfig('cronofykey')
		calendarID = self.getConfig('calendarID')
		cronofy = pycronofy.Client(access_token=key)

		timezone_id = 'US/Pacific'

		tz = pytz.timezone(timezone_id)
		now = datetime.now(tz=tz)
		from_date = now.strftime("%Y-%m-%d")
		two_days = now + timedelta(days=2)
		to_date = two_days.strftime("%Y-%m-%d")



		all_events = cronofy.read_events(calendar_ids=(calendarID,),
										 from_date=from_date,
										 to_date=to_date,
										 tzid=timezone_id,
										 localized_times=True
										 ).all()

		event_list = []
		for event in all_events:
			event_end = datetime.strptime(event["end"]["time"], "%Y-%m-%dT%H:%M:%S%z")
			self.logInfo(f'Event: {event["summary"]}')
			if event_end > now:
				self.logInfo(f'Added')
				event_list.append(event)

		self.updateConfig(key="eventList", value=json.dumps(event_list))

	def checkVerification(self):
		self.logInfo('Checking for verification.')

		lastVerifiedEventID = self.getConfig('lastVerifiedEventID')

		eventList = json.loads(self.getConfig('eventList'))
		timezone_id = 'US/Pacific'

		tz = pytz.timezone(timezone_id)
		now = datetime.now(tz=tz)
		currentEvent = {}
		for event in eventList:
			event_start = datetime.strptime(event["start"]["time"], "%Y-%m-%dT%H:%M:%S%z")
			event_end = datetime.strptime(event["end"]["time"], "%Y-%m-%dT%H:%M:%S%z")
			if event_start <= now and event_end > now:
				currentEvent = event
				break
		currentEventOutput = json.dumps(currentEvent)
		self.logInfo(f'currentEvent: {currentEventOutput}')
		self.logInfo(f'lastVerifiedEventID: {lastVerifiedEventID}')

		# Verification Required
		if currentEvent and lastVerifiedEventID != currentEvent["event_uid"]:
			self.askQuestion(currentEvent)
		# No verification Required
		else:
			self.ThreadManager.doLater(interval=60, func=self.checkVerification)


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

	def askQuestion(self, event: {}):
		self.ask(
			text = f'The meeting {event["summary"]} should have begun. Are the attendee\'s here?',
			intentFilter=[self._INTENT_ATTENDEE_THERE],
			customData={
				'EventID': event['event_uid']
			}
		)

	@IntentHandler('NextMeeting')
	def nextMeeting(self, session: DialogSession, **_kwargs):
		eventList = json.loads(self.getConfig('eventList'))
		timezone_id = 'US/Pacific'

		tz = pytz.timezone(timezone_id)
		now = datetime.now(tz=tz)
		nextEvent = {}
		for event in eventList:
			event_start = datetime.strptime(event["start"]["time"], "%Y-%m-%dT%H:%M:%S%z")
			if event_start > now:
				nextEvent = event
				break
		eventOutput = json.dumps(nextEvent)
		self.logInfo(f'event2: {eventOutput}')

		if not nextEvent:
			self.endDialog(session.sessionId, f'No events are scheduled.')
		else:
			time = self.formatTimeToVoice(time=nextEvent["start"]["time"])
			self.endDialog(session.sessionId, f'The next event is {nextEvent["summary"]}. It will begin at {time}')

		self.askQuestion(nextEvent)

	@IntentHandler('AttendeeThere')
	def attendeeThere(self, session: DialogSession, **_kwargs):
		self.endSession(session.sessionId)
		response = "no"
		if self.Commons.isYes(session):
			response = "yes"
			self.updateConfig(key="lastVerifiedEventID", value=session.customData["EventID"])
			self.say(f'Thank you enjoy your meeting.')
			self.ThreadManager.doLater(interval=60, func=self.checkVerification)
		else:
			verification_count = self.getConfig('verificationCount') + 1
			verification_max_count = self.getConfig('verificationMaxCount')

			if verification_count == verification_max_count:
				# Release the room
				self.logInfo(f'Room has been released. EventID: {session.customData["EventID"]}')
				self.updateConfig(key="lastVerifiedEventID", value=session.customData["EventID"])
				self.updateConfig(key="verificationCount", value=0)
			else:
				self.updateConfig(key="verificationCount", value=verification_count)
				verification_wait_time = self.getConfig('verificationWaitTime')
				self.ThreadManager.doLater(interval=verification_wait_time, func=self.checkVerification)

		self.logInfo(f'yes no response: {response}')

	@IntentHandler('DanceDebug')
	def danceDebug(self, session:DialogSession, **_kwargs):
		self.logInfo(f'god I hope this works.')