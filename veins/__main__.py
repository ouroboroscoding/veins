# coding=utf8
""" Veins

Main entry into the package
"""

__author__		= "Chris Nasr"
__copyright__	= "OuroborosCoding"
__version__		= "1.0.0"
__maintainer__	= "Chris Nasr"
__email__		= "chris@ouroboroscoding.com"
__created__		= "2017-06-26"

# Ouroboros modules
from config import config

# Import python modules
from collections import OrderedDict
import threading

# Import pip modules
from gevent import monkey; monkey.patch_all()
from geventwebsocket import Resource, WebSocketServer

# Import module
from . import init as wsInit, \
				stop as wsStop, \
				thread as wsThread, \
				SyncApplication

def cli():
	"""CLI

	Called from the command line to run from the current directory

	Returns:
		uint
	"""

	# Get config
	dConf = config.veins({
		'host': '0.0.0.0',
		'port': 8699,
		'verbose': False
	})

	# Init the sync application
	wsInit(dConf['verbose'])

	# Start the Redis thread
	try:
		if dConf['verbose']:
			print('Starting the Redis thread')
		thread = threading.Thread(target = wsThread)
		thread.daemon = True
		thread.start()
	except Exception as e:
		print('Failed to start Redis thread: %s' % str(e))

	# Create the websocket server
	if dConf['verbose']:
		print('Starting the WebSocket server on %s:%d' % (
			dConf['host'], dConf['port']
		))
	oServer = WebSocketServer(
		(dConf['host'], dConf['port']),
		Resource(OrderedDict([ ( '/', SyncApplication ) ]))
	)

	# Run the server forever
	try:
		oServer.serve_forever()
	except KeyboardInterrupt:
		wsStop()
		pass

	# Shutdown the server
	oServer.close()

# Only run if called directly
if __name__ == '__main__':
	exit(cli())