import json
import pycronofy
from datetime import datetime, timedelta
import pytz
import requests
import uuid

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
		serial = self.getserial()
		self.logInfo(f'Serial Number: {serial}')
		response = requests.get(f'https://cxweif56vl.execute-api.us-west-2.amazonaws.com/prod/endpoint/{serial}/config')
		self.logInfo(f'Status Code: {response.status_code}')
		if response.ok:
			self.logInfo(f'Response: {response.content}')
			config = json.loads(response.content)
			if config:
				self.setConfig(name=config['Name'],
							   calendarID=config['CalendarID'],
							   verificationWaitTime=config['VerificationWaitTime'],
							   verificationMaxCount=config['VerificationMaxCount'])
				self.loadCalendar()
				self.updateConfig(key="verificationCount", value=0)
				self.checkVerification()
			else:
				self.logInfo(f'No Configuration')
				self.say(f'The serial number is {serial}')

	def setConfig(self, name: str, calendarID: str, verificationWaitTime: int, verificationMaxCount: int):
		self.updateConfig(key="name", value=name)
		self.updateConfig(key="calendarID", value=calendarID)
		self.updateConfig(key="verificationWaitTime", value=verificationWaitTime)
		self.updateConfig(key="verificationMaxCount", value=verificationMaxCount)

	def loadCalendar(self):
		calendar_refresh_time = int(self.getConfig('calendarRefreshTime'))
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

		all_events_output = json.dumps(all_events)
		self.logInfo(f'{all_events_output}')
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

		if currentEvent:
			self.logInfo(f'currentEventID: {currentEvent["event_uid"]}, currentEventName: {currentEvent["summary"]}')
		else:
			self.logInfo(f'No current event.')

		self.logInfo(f'lastVerifiedEventID: {lastVerifiedEventID}')

		# Verification Required
		if currentEvent and lastVerifiedEventID != currentEvent["event_uid"]:
			self.askQuestion(currentEvent)
		# No verification Required
		else:
			self.ThreadManager.doLater(interval=60, func=self.checkVerification)

	def askQuestion(self, event: {}):
		self.logInfo(f'Asking the question')
		self.ask(
			text = f'The meeting {event["summary"]} should have begun. Are the attendee\'s here?',
			intentFilter=[self._INTENT_ATTENDEE_THERE],
			customData={
				'EventID': event['event_uid']
			}
		)

	################################################
	#		 		Intents						   #
	################################################

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
		self.logInfo(f'Answering the question.')
		self.endSession(session.sessionId)
		if self.Commons.isYes(session):
			self.logInfo(f'User responded yes.')
			self.updateConfig(key="lastVerifiedEventID", value=session.customData["EventID"])
			self.say(f'Thank you enjoy your meeting.')
			self.ThreadManager.doLater(interval=60, func=self.checkVerification)
		else:
			self.logInfo(f'User responded no.')
			verification_count = int(self.getConfig('verificationCount')) + 1
			verification_max_count = int(self.getConfig('verificationMaxCount'))

			if verification_count == verification_max_count:
				# Release the room
				self.deleteEvent(eventID=session.customData["EventID"])
				self.logInfo(f'Max count reached.')
				self.logInfo(f'Room has been released. EventID: {session.customData["EventID"]}')
				self.updateConfig(key="lastVerifiedEventID", value=session.customData["EventID"])
				self.updateConfig(key="verificationCount", value=0)
				self.ThreadManager.doLater(interval=60, func=self.checkVerification)
			else:
				self.logInfo(f'Max count not reached.')
				self.updateConfig(key="verificationCount", value=verification_count)
				verification_wait_time = int(self.getConfig('verificationWaitTime'))
				self.ThreadManager.doLater(interval=verification_wait_time, func=self.checkVerification)

	@IntentHandler('DanceDebug')
	def danceDebug(self, session:DialogSession, **_kwargs):
		self.logInfo(f'god I hope this works.')

	################################################
	#		 		Utilities					   #
	################################################
	def getserial(self):
		# Extract serial from cpuinfo file
		cpuserial = "0000000000000000"
		try:
			f = open('/proc/cpuinfo', 'r')
			for line in f:
				if line[0:6] == 'Serial':
					cpuserial = line[10:26]
			f.close()
		except:
			cpuserial = "ERROR000000000"

		return cpuserial.lstrip("0").upper()

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

	def deleteEvent(self, eventID: str):
		key = self.getConfig('cronofykey')
		calendarID = self.getConfig('calendarID')
		cronofy = pycronofy.Client(access_token=key)
		cronofy.delete_event(calendar_id=calendarID, event_id=eventID)

	def createEvents(self):
		key = self.getConfig('cronofykey')
		calendar_id = self.getConfig('calendarID')
		cronofy = pycronofy.Client(access_token=key)
		timezone_id = 'US/Pacific'

		# First delete events.
		cronofy.delete_all_events(calendar_ids=(calendar_id))

		event_id = 'finalprojectalice-%s' % uuid.uuid4()
		event = {
			'event_id': event_id,
			'summary': 'Current Event',
			'description': 'Here is the summary of the current event.',
			'start': datetime.utcnow(),
			'end': datetime.utcnow() + timedelta(minutes=15),
			'tzid': timezone_id,
			'location': {
				'description': 'Machine Room'
			}
		}

		cronofy.upsert_event(calendar_id=calendar_id, event=event)

		event_id = 'finalprojectalice-%s' % uuid.uuid4()
		event = {
			'event_id': event_id,
			'summary': 'Next Event',
			'description': 'Here is the summary of the next event.',
			'start': datetime.utcnow() + timedelta(minutes=30),
			'end': datetime.utcnow() + timedelta(minutes=45),
			'tzid': timezone_id,
			'location': {
				'description': 'Machine Room'
			}
		}

		cronofy.upsert_event(calendar_id=calendar_id, event=event)