import json

from core.base.model.Intent import Intent
from core.base.model.Module import Module
from core.dialog.model.DialogSession import DialogSession


class finalprojectalice(Module):
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
		self.randomlySpeak(init=True)

	def randomlySpeak(self, init: bool = False):
		rnd = 10
		self.ThreadManager.doLater(interval=rnd, func=self.randomlySpeak)
		self.logInfo(f'Scheduled next random speaking in {rnd} seconds')

		if not init and not self.UserManager.checkIfAllUser('goingBed') and not self.UserManager.checkIfAllUser('sleeping'):
			self.say(self.randomTalk(f'randomlySpeakAnger'), siteId='all')
