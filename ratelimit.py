#!/usr/bin/env python3

"""

   Run this file to check your rate limit statuses.
   I run this in Sublime Text (*REPL* python) and use
   cmd+f to find the limit I'm looking for.

"""


from twitter import *
from t import ACCESS_TOKEN_KEY, ACCESS_TOKEN_SECRET, CONSUMER_KEY, CONSUMER_SECRET

t = Twitter(auth=OAuth(ACCESS_TOKEN_KEY, ACCESS_TOKEN_SECRET, CONSUMER_KEY, CONSUMER_SECRET))

def main():

	print(t.application.rate_limit_status())
	return

main()
