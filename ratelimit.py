#!/usr/bin/env python3

"""

	Run this file to check your rate limit statuses.
	I run this in Sublime Text (*REPL* python) and use
	cmd+f to find the limit I'm looking for.

	For Google Sheets, check your dashboard: https://console.developers.google.com/apis/enabled

"""

from twitter import Twitter, OAuth
from t import ACCESS_TOKEN_KEY, ACCESS_TOKEN_SECRET, CONSUMER_KEY, CONSUMER_SECRET

t = Twitter(auth=OAuth(ACCESS_TOKEN_KEY, ACCESS_TOKEN_SECRET, CONSUMER_KEY, CONSUMER_SECRET))

def main():

	print(t.application.rate_limit_status())
	return

main()
