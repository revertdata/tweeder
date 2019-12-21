#!/usr/bin/env python3

# =======================================
# =           Twitter cleaner           =
# =   https://twitter.com/telepathics   =
# =   https://twitter.com/revertdata    =
# =======================================

import time
import pytz
from datetime import datetime, timezone
from dateutil.relativedelta import relativedelta

from httplib2 import Http
from oauth2client import file, client, tools
from urllib.request import urlopen, HTTPError

import re
import json

from twitter import *
from t import ACCESS_TOKEN_KEY, ACCESS_TOKEN_SECRET, CONSUMER_KEY, CONSUMER_SECRET

from googleapiclient.discovery import build
from g import SCOPES, SPREADSHEET_ID, RANGE_NAME

# =============================================
# =           Account Handler Class           =
# =============================================
"""

	TODO:
	- Unfollow users

"""

class AccountHandler(object):
	def __init__(self):
		self.t = Twitter(auth=OAuth(ACCESS_TOKEN_KEY, ACCESS_TOKEN_SECRET, CONSUMER_KEY, CONSUMER_SECRET))
		self.feed = []

	# -----------  Get Recent Tweets -----------
	def get_recent_tweets(self, screen_name):
		t = self.t
		feed = t.statuses.user_timeline(screen_name=screen_name, count=200, exclude_replies=True, trim_user=True)

		self.feed = feed
		return feed

	# -----------  Get User IDs from Tweet Interactions  -----------
	def get_tweet_interaction_user_IDs(self, action, post_id):
		t = self.t

		try:
			json_data = urlopen('https://twitter.com/i/activity/' + str(action) + '_popup?id=' + str(post_id)).read().decode('utf-8')
			found_ids = re.findall(r'data-user-id=\\"+\d+', json_data)
			unique_ids = list(set([re.findall(r'\d+', match)[0] for match in found_ids]))
			return unique_ids
		except HTTPError:
			return False

	# -----------  Get old tweets from tweet.json  -----------
	def get_old_tweets(self, years_ago):
		past_time = datetime.now() - relativedelta(years=years_ago)
		utc=pytz.UTC
		old_tweets = []

		with open('tweet.json', 'r') as tweets:
			tweetlist = json.load(tweets)
			for tweet in tweetlist:
				try:
					created_at = datetime.strptime(tweet["created_at"],"%a %b %d %H:%M:%S %z %Y")
					old_enough = created_at.replace(tzinfo=utc) < past_time.replace(tzinfo=utc)
					if old_enough:
						old_tweets.append(tweet)
				except:
					continue
		return old_tweets

	# -----------  Delete tweets older than 2 years  -----------
	def delete_archived_tweets(self):
		t = self.t
		old_tweets = self.get_old_tweets(2)

		for tweet in old_tweets:
			t.statuses.destroy(_id=tweet['id_str'])
			print(tweet['full_text'])
			print('DELETED ' + tweet['id_str'] + ' (' + created_at.strftime("%a %b %d %H:%M:%S %z %Y") + ')')
			print()

		return True

	# -----------  Delete tweets without interactions  -----------
	def delete_tweets_without_interactions(self):
		t = self.t
		old_tweets = self.get_old_tweets(1)

		for tweet in old_tweets:
			# check if there are interactions
			interactions = int(tweet["favorite_count"])+int(tweet["retweet_count"])
			if interactions == 0:
				t.statuses.destroy(_id=tweet["id_str"])
				print(tweet['full_text'] + ' (' + str(interactions) + ' interactions) ')
				print('DELETED ' + tweet['id_str'] + ' (' + created_at.strftime("%a %b %d %H:%M:%S %z %Y") + ')')
				print()

		return True

# ============================================
# =           Exempt Handler Class           =
# ============================================

class ExemptHandler(object):
	def __init__(self):
		self.service = self.g_auth()
		self.whitelist = self.refresh_whitelist()

		return

	# -----------  Basic Google Authentication  -----------
	def g_auth(self):
		store = file.Storage('token.json')
		creds = store.get()
		if not creds or creds.invalid:
			flow = client.flow_from_clientsecrets('credentials.json', SCOPES)
			creds = tools.run_flow(flow, store)
		service = build('sheets', 'v4', http=creds.authorize(Http()))

		return service

	def refresh_whitelist(self):
		result = service.spreadsheets().values().get(
			spreadsheetId=SPREADSHEET_ID,
			range=RANGE_NAME
		).execute()
		values = result.get('values', [])

		if not values:
			return False
		else:
			return values

	# -----------  Add User to Whitelist via Category Spreadsheet  -----------
	def add_users(self, category, screen_names):
		service = self.service
		resource = {"values": screen_names}
		CAT_RANGE = category.upper() + "!A:A";
		service.spreadsheets().values().append(
			spreadsheetId=SPREADSHEET_ID,
			range=CAT_RANGE,
			body=resource,
			valueInputOption="USER_ENTERED"
		).execute()

		return

# =========================================
# =           Tweeder Functions           =
# =========================================
"""

	TODO:
	- Compare following list to whitelist
	- Create a tweet ID whitelist (ex. for blog posts)
	- Add tweets with > 100 interactions to whitelist

"""

class Tweeder(object):
	def __init__(self, tw, sheet):
		self.tw = tw
		self.sheet = sheet
		self.whitelist = []

	def refresh_whitelist(self):
		tw = self.tw
		sheet = self.sheet
		whitelist = sheet.refresh_whitelist()

		for user in sheet.whitelist:
			if user == []:
				continue
			whitelist.append(user[0])

		self.whitelist = whitelist
		return whitelist

	def add_recent_interactions_to_whitelist(self):
		tw = self.tw
		sheet = self.sheet

		recent_tweets = tw.get_recent_tweets('telepathics')
		for tweet in recent_tweets:
			tid = tweet['id']
			actions = ['favorited', 'retweeted']
			for action in actions:
				uids = tw.get_tweet_interaction_user_IDs(action, tid)
				for uid in uids:
					t = tw.t
					uinfo = t.users.show(user_id=uid)
					uscreen_name = uinfo['screen_name'].lower()
					sheet.add_users(action, [[uscreen_name]])
					time.sleep(15)

# ======  End of Tweeder Functions  =======

def main():
	# tw = AccountHandler()
	# sheet = ExemptHandler()
	# Tweeder = Tweeder(tw, sheet)

	# More code that integrates tw & sheet

	return

if __name__ == '__main__':
	main()
