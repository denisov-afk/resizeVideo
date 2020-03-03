"""All settings was here"""

# AMQP settings
BROKER = 'amqp://guest:guest@localhost:5672/%2F'
EXCHANGE = 'suptitle'
QUEUE_IN = 'videoresizer.in'
QUEUE_OUT = 'videoresizer.out'
QUEUE_STT = 'STT.in'
ROUTING_KEY = 'suptitle.videoresizer.in'
APP_ID = 'suptitle.videoresizer'
ALLOWED_APP_ID = ['suptitle.website',
                  ]

# videoresizer settings
CREDITIONALS_JSON = 'steady-cat-269313-8b90bcfb5b51.json'
FIREBASE_STORAGE_BUCKET = 'subtitles-a6e05.appspot.com'

# log settings
LOG_FORMAT = '%(levelname) -10s %(asctime)s %(name) -30s %(funcName) -35s %(lineno) -5d: %(message)s'
LOG_LEVEL = 'INFO'

