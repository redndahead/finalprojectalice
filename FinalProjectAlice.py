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
		response = requests.get(f'https://cxweif56vl.execute-api.us-west-2.amazonaws.com/prod/endpoint/{serial}/config')
		self.updateConfig(key="inVerification", value=False)
		if response.ok:
			self.logInfo(f'Configuration Response: {response.content}')
			config = json.loads(response.content)
			if config:
				self.setConfig(name=config['Name'],
							   calendarID=config['CalendarID'],
							   verificationWaitTime=config['VerificationWaitTime'],
							   verificationTimeout=config['VerificationTimeout'])
				# Only used during testing.
				self.createEvents()

				self.loadCalendar()
				self.checkVerification()
			else:
				self.say(f'The device id is {serial}')

	def setConfig(self, name: str, calendarID: str, verificationWaitTime: int, verificationTimeout: int):
		self.updateConfig(key="name", value=name)
		self.updateConfig(key="calendarID", value=calendarID)
		self.updateConfig(key="verificationWaitTime", value=verificationWaitTime)
		self.updateConfig(key="verificationTimeout", value=verificationTimeout)


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

		# Always loop
		self.ThreadManager.doLater(interval=60, func=self.checkVerification)

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
			self.logInfo(f'currentEventID: {currentEvent["event_id"]}, currentEventName: {currentEvent["summary"]}')
		else:
			self.logInfo(f'No current event.')

		self.logInfo(f'lastVerifiedEventID: {lastVerifiedEventID}')

		# Verification Required
		if currentEvent and lastVerifiedEventID != currentEvent["event_id"]:
			self.askQuestion(currentEvent)
			if not self.getConfig('inVerification'):
				self.updateConfig(key="inVerification", value=True)
				self.isPassedTime(currentEvent)

	def askQuestion(self, event: {}):
		self.logInfo(f'Asking the question')

		self.ask(
			text = f'The meeting {event["summary"]} should have begun. Are the attendee\'s here?',
			intentFilter=[self._INTENT_ATTENDEE_THERE],
			customData={
				'EventID': event['event_id']
			}
		)

	def isPassedTime(self, event):
		self.logInfo("In isPassedtime");
		last_verified_event_id = self.getConfig('lastVerifiedEventID')
		self.logInfo("Last Verified: " + last_verified_event_id + ", Current ID: " + event['event_id'])
		if (last_verified_event_id != event['event_id']):
			verification_timeout = int(self.getConfig('verificationTimeout'))
			expire_length = verification_timeout + 50
			self.logInfo(f'expire length: {expire_length}')
			event_start = datetime.strptime(event['start']['time'], "%Y-%m-%dT%H:%M:%S%z")
			event_timeout = event_start + timedelta(seconds=expire_length)

			timezone_id = 'US/Pacific'

			tz = pytz.timezone(timezone_id)
			now = datetime.now(tz=tz)

			if now >= event_timeout:
				# Release the room
				self.deleteEvent(eventID=event["event_id"])
				self.stopVerification(eventID=event["event_id"], action="release", type="")
				self.logInfo(f'Expire time reached')
				self.logInfo(f'Room has been released. EventID: {event["event_id"]}')


				self.say(f'The room reservation has been removed.')
			else:
				self.logInfo(f'Continue checking')
				self.ThreadManager.doLater(interval=4, func=self.isPassedTime, args=[event])

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
			self.stopVerification(eventID=session.customData["EventID"], action="verify", type="voice")
			self.say(f'Thank you enjoy your meeting.')

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

	def getCurrentNextEvent(self):
		calendarID = self.getConfig('calendarID')

		if (calendarID):
			last_verified_event_id = self.getConfig('lastVerifiedEventID')
			eventList = json.loads(self.getConfig('eventList'))
			timezone_id = 'US/Pacific'

			tz = pytz.timezone(timezone_id)
			now = datetime.now(tz=tz)
			output = []
			placeholder1 = {
				'id': "",
				'time': "",
				'summary': "No Current Event",
				'description': "",
				'verified': True
			}

			placeholder2 = {
				'id': "",
				'time': "",
				'summary': "No Future Event Scheduled",
				'description': ""
			}
			for event in eventList:
				eventItem = {}
				event_start = datetime.strptime(event["start"]["time"], "%Y-%m-%dT%H:%M:%S%z")
				event_start_formatted = event_start.strftime("%-I:%M %p")
				event_start_date = event_start.strftime("%-m/%-d/%y")
				event_end = datetime.strptime(event["end"]["time"], "%Y-%m-%dT%H:%M:%S%z")
				event_end_formatted = event_end.strftime("%-I:%M %p")

				eventItem['id'] = event['event_id']
				eventItem['time'] = event_start_date + " " + event_start_formatted + " - " + event_end_formatted
				eventItem['summary'] = event['summary']
				eventItem['description'] = event['description']

				if event_start <= now:
					if last_verified_event_id == event['event_id']:
						eventItem['verified'] = True
					else:
						eventItem['verified'] = False
				elif len(output) == 0:
					output.append(placeholder1)

				output.append(eventItem)

				if len(output) == 2:
					break

			if len(output) == 0:
				output.append(placeholder1)
				output.append(placeholder2)
		else:
			output = False

		return output

	def stopVerification(self, eventID: str, action: str, type: str):
		self.updateConfig(key="lastVerifiedEventID", value=eventID)
		self.updateConfig(key="inVerification", value=False)

		postData = {
			'DeviceID': self.getserial(),
			'Action': action,
			'Type': type,
			'Timestamp': '2019-12-08 12:00:00'
		}
		requests.post("https://cxweif56vl.execute-api.us-west-2.amazonaws.com/prod/statistics", data=json.dumps(postData))

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
			'summary': 'Main Website Demo',
			'description': 'Show off what\'s new on the main website.',
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
			'summary': 'Salesforce Deployment Stand-up',
			'description': 'Daily stand-up of the Salesforce Deployment project.',
			'start': datetime.utcnow() + timedelta(minutes=30),
			'end': datetime.utcnow() + timedelta(minutes=45),
			'tzid': timezone_id,
			'location': {
				'description': 'Machine Room'
			}
		}

		cronofy.upsert_event(calendar_id=calendar_id, event=event)