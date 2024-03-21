# coding=utf8
""" Veins Service

Handles syncing up changes using websockets and sessions
"""

__author__		= "Chris Nasr"
__copyright__	= "OuroborosCoding"
__version__		= "1.0.0"
__maintainer__	= "Chris Nasr"
__email__		= "chris@ouroboroscoding.com"
__created__		= "2017-06-26"

# Ouroboros imports
from config import config
from nredis import nr

# Python imports
from http.cookies import SimpleCookie
import jsonb
from urllib.parse import unquote

# Pip imports
from geventwebsocket import WebSocketApplication, WebSocketError
from redis.exceptions import ConnectionError

# Init the global vars
_r = None
_r_pubsub = None
_r_clients = {}
_verbose = False

# Init function
def init(verbose: bool = False):
	"""Init

	Called to initialize the service

	Arguments:
		verbose (bool): Optional verbose argument
			if set to True, the service will print out what's going on

	Returns:
		None
	"""

	# Import the global redis instance
	global _r, _r_pubsub, _verbose

	# Create a new Redis instance
	_r = nr(config.veins.redis('veins'))

	# Get the pubsub instance
	_r_pubsub = _r.pubsub()

	# Subscribe to an empty channel just to get things started
	_r_pubsub.subscribe('sync')

	# Set the verbose flag
	_verbose = verbose

# Stop function
def stop():
	"""Stop

	Unsubscribes from all messages and disconnects all websockets

	Returns:
		None
	"""

	global _r, _r_pubsub

	if _verbose:
		print('close called')

	# Go through each tracking code
	for track in _r_clients:

		# Unsubscribe
		_r_pubsub.unsubscribe(track)

		# Go through each websocket
		for i in range(len(_r_clients[track])):

			# If it's not closed, close it
			if not _r_clients[track][i].ws.closed:
				_r_clients[track][i].ws.close()

	# Delete the connections
	_r_pubsub.close()
	del _r_pubsub
	del _r

# Redis thread
def thread():
	"""Thread

	Listens for incoming redis pubsub messages

	Returns:
		None
	"""

	if _verbose:
		print('Threading starting')

	try:

		# Try to get messages
		for d in _r_pubsub.listen():

			if _verbose:
				print('Received pubsub message: %s' % str(d))

			# If the message is real data and not subscribe/ubsubscribe
			if d['type'] == 'message':

				# Convert the channel to a unicode string
				d['channel'] = d['channel'].decode('utf-8')

				# If we have the channel
				if d['channel'] in _r_clients:

					# Forward the message to each socket
					for ws in _r_clients[d['channel']]:
						ws.on_publish(d['data'].decode('utf-8'))

	except Exception as e:
		print(str(e))

	if _verbose:
		print('Threading finished')

# The application class
class SyncApplication(WebSocketApplication):
	"""Sync Application

	This class will handle all joined connections to the server
	"""

	# fail method
	def _fail(self, code: int = 0, msg: any = 'websocket failure'):
		"""Fail

		Called to close the current connection with the default error message

		Arguments:
			code (uint): The error code
			msg (str): The error msg

		Returns:
			None
		"""

		self.ws.send(jsonb.encode({
			'error': {
				'code': code,
				'msg': msg
			}
		}))
		self.ws.close()

	# on close method
	def on_close(self, reason: str = None):
		"""On Close

		Called when an existing client websocket is closed

		Arguments:
			reason (str): The reason the connection closed?

		Returns:
			None
		"""

		if _verbose:
			print('Connection closed: %s' % reason)

		# If we have any subpubs, ubsubscribe
		for track in self.tracking:

			# If we have a subpub, ubsubscribe
			try:
				if _r_clients[track].length == 1:
					_r_pubsub.unsubscribe(track)

			except:
				pass

			# If we're in the list of clients
			try:
				_r_clients[track].remove(self)
			except:
				pass

	# on message method
	def on_message(self, message: str):
		"""On Message

		Called when a new message is received from an existing client websocket

		Arguments:
			message (str): The message from the client encoded as JSON

		Returns:
			None
		"""

		if _verbose: print('Message received: %s' % str(message))

		# If it's None, we do nothing
		if not message:
			return

		# Catch any potential exceptions
		try:

			# Convert the JSON data
			try:
				messages = jsonb.decode(message)
			except ValueError as e:
				if _verbose:
					print('Failed to decode JSON: "%s"' % message)
				return self._fail(1, 'Failed to decode JSON: "%s"' % message)

			# If the message is not a list
			if not isinstance(messages, list):
				messages = [ messages ]

			# Go through each message
			for data in messages:

				# If the message has no type
				if '_type' not in data:
					if _verbose:
						print('Type missing from message: "%s"' % message)
					return self._fail(
						2,
						'Type missing from message: "%s"' % message
					)

				# If it's a connect message
				if data['_type'] == 'connect':

					# If the message has no key
					if 'key' not in data:
						if _verbose:
							print('Key missing from connect message: "%s"' % \
			 					message
							)
						return self._fail(
							3,
							'Key missing from connect message: "%s"' % message
						)

					# Fetch the data associated with the key in the message
					sConnect = _r.get(data['key'])

					# If the key doesn't exist
					if not sConnect:
						if _verbose:
							print('Key found no data: \'%s\'' % data['key'])
						return self._fail(
							4,
							'Key found no data: \'%s\'' % data['key']
						)

					# Delete the key
					_r.delete(data['key'])

					# Convert the JSON data
					try:
						dConnect = jsonb.decode(sConnect)
					except ValueError as e:
						if _verbose:
							print('Failed to decode JSON: "%s"' % sConnect)
						return self._fail(
							5,
							'Failed to decode JSON: "%s"' % sConnect
						)

					# If the session ID doesn't exist
					if 'session' not in dConnect:
						if _verbose:
							print('Session ID missing: "%s"', sConnect)
						return self._fail(
							6,
							'Session ID missing: "%s"' % sConnect
						)

					# If the session ID doesn't match
					if dConnect['session'] != self.token:
						if _verbose:
							print('Session IDs don\'t match: "%s" != "%s"' % (
								dConnect['session'], self.token
							))
						return self._fail(
							7,
							'Session IDs don\'t match: "%s" != "%s"' % (
								dConnect['session'], self.token
							)
						)

					# Allow further messages
					self.authorized = True

					# Return OK
					self.ws.send('authorized')

				# Else if it's a message to ping
				elif data['_type'] == 'ping':

					# Make sure we are authorized
					if not self.authorized:
						if _verbose:
							print('Received ping message before authorization')
						self._fail(
							8,
							'Received ping message before authorization'
						)

					# Ping redis
					#_r.ping()

					# Respond to the request
					self.ws.send('pong')

				# Else if it's a message to track something new
				elif data['_type'] == 'track':

					# Make sure we are authorized
					if not self.authorized:
						if _verbose:
							print('Received track message before authorization')
						self._fail(
							8,
							'Received track message before authorization'
						)

					# Check for a key
					if 'key' not in data:
						if _verbose:
							print('Missing `key` in message: ""' % message)
						return self._fail(
							9,
							'Missing `key` in message: ""' % message
						)

					# Make sure the data is a string
					if not isinstance(data['key'], str):
						data['key'] = str(data['key'])

					# Add the key to the client list
					try:
						_r_clients[data['key']].append(self)
					except:
						_r_clients[data['key']] = [self]
						_r_pubsub.subscribe(data['key'])

					# Add it to the list on this socket
					if _verbose:
						print(
							'Successfully started tracking: "%s"' % data['key']
						)
					self.tracking.append(data['key'])

				# Else if it's a message to stop tracking something
				elif data['_type'] == 'untrack':

					# Make sure we are authorized
					if not self.authorized:
						if _verbose:
							print(
								'Received untrack message before authorization'
							)
						self._fail(
							8,
							'Received untrack message before authorization'
						)

					# Check for the key
					if 'key' not in data:
						if _verbose:
							print('Missing `key` in message: ""' % message)
						return self._fail(
							9,
							'Missing `key` in message: ""' % message
						)

					# Make sure the data is a string
					if not isinstance(data['key'], str):
						data['key'] = str(data['key'])

					# If the key exists in the clients
					if data['key'] in _r_clients:

						# If the socket exists, delete it
						if self in _r_clients[data['key']]:
							_r_clients[data['key']].remove(self)

						# If there's no nore clients
						if not len(_r_clients[data['key']]):
							del _r_clients[data['key']]
							_r_pubsub.unsubscribe(data['key'])

					# Remove the list on this socket
					if _verbose:
						print(
							'Successfully stopped tracking: "%s"' % data['key']
						)
					self.tracking.remove(data['key'])

				# Else this is an invalid message
				else:
					if _verbose:
						print('Invalid message type: "%s"' % str(data['_type']))
					return self._fail(
						10,
						'Invalid message type: "%s"' % str(data['_type'])
					)

		# Catch any redis connection errors
		except ConnectionError as e:
			print(str(e))
			self.ws.close()

		# Catch any websocket errors
		except WebSocketError as e:
			print(str(e))
			self.ws.close()

	# on open method
	def on_open(self):
		"""On Open

		Will be called when a new client connects to the server
		"""

		if _verbose:
			print('on_open called')

		# Init instance variables
		self.authorized = False
		self.tracking = []

		# If there is no cookie
		if 'HTTP_COOKIE' not in self.ws.environ:
			if _verbose: print('HTTP_COOKIE missing')
			return self._fail(11, 'HTTP_COOKIE missing')

		# If the cookie lacks the session value
		oCookies = SimpleCookie()
		oCookies.load(self.ws.environ['HTTP_COOKIE'])
		dCookies = { k:v.value for k,v in oCookies.items() }
		if _verbose:
			print(dCookies)
		if '_session' not in dCookies:
			if _verbose:
				print('_session not in cookies')
			return self._fail(12, '_session not in cookies')

		# Store the session ID
		self.token = unquote(dCookies['_session'])

	# on publish method
	def on_publish(self, message):
		"""On Publish

		Called when new pubsub messages arrive on a channel this web socket
		is subscribed to

		Arguments:
			message (str): A published message

		Returns:
			None
		"""
		if _verbose:
			print('on_publish called with message: %s' % message)
		self.ws.send(message)