import json
API_CREDS_FILE = 'D:/OneDrive/Studies/forex_python/api_creds.json'

# Load API credentials
with open(API_CREDS_FILE) as json_file:
    apicreds = json.load(json_file)


API_KEY = apicreds['API_KEY']
ACCOUNT_ID = apicreds['ACCOUNT_ID']
OANDA_URL = apicreds['OANDA_URL']