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

from picker import *
from httplib2 import Http
from oauth2client import file, client, tools
from urllib.request import urlopen, HTTPError

import sys
import re
import json
import random

from twitter import *
from t import ACCESS_TOKEN_KEY, ACCESS_TOKEN_SECRET, CONSUMER_KEY, CONSUMER_SECRET

from googleapiclient.discovery import build
from g import SCOPES, SPREADSHEET_ID

STARTC = '\033[90m'
ENDC = '\033[0m'

# =============================================
# =           Account Handler Class           =
# =============================================

class AccountHandler(object):
	def __init__(self):
		self.t = Twitter(auth=OAuth(ACCESS_TOKEN_KEY, ACCESS_TOKEN_SECRET, CONSUMER_KEY, CONSUMER_SECRET))
		self.feed = []
		self.friends = []

	# -----------  Get Recent Tweets -----------
	def get_recent_tweets(self, screen_name):
		t = self.t
		feed = t.statuses.user_timeline(screen_name=screen_name, count=200, exclude_replies=True, trim_user=True)

		self.feed = feed
		return feed

	# -----------  Get Twitter Followers  -----------
	def get_twitter_friends(self):
		t = self.t
		friends = t.friends.list(count=200, skip_status=True, include_user_entities=False)

		self.friends = friends
		return friends

	# -----------  Get Twitter Lists  -----------
	def get_twitter_lists(self):
		t = self.t
		owned_lists = t.lists.ownerships(count=25)["lists"]

		return owned_lists

	# -----------  Get List Members  -----------
	def get_twitter_list_members(self, list_id):
		t = self.t
		screen_names = t.lists.members(list_id=list_id, count=5000, include_entities=False, skip_status=True)
		return True

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

	# -----------  Unfollow users on Twitter  -----------
	def unfollow_twitter_user(self, screen_name):
		t = self.t

		t.friends.remove(screen_name)
		t.friendships.destroy(screen_name=screen_name)

		return True

	# -----------  Add Users to Twitter List  -----------
	def add_users_to_list(self, screen_names, list_id, list_slug, owner_screen_name):
		t = self.t

		# can only add ~100 users to a list at a time.
		chunks = [screen_names[x:x+100] for x in range(0, len(screen_names), 100)]
		for chunk in chunks:
			t.lists.members.create_all(
				list_id=list_id,
				slug=list_slug,
				owner_screen_name=owner_screen_name,
				screen_name=chunk
			)
			print("Added the following users to the list '" + list_slug + "'.")
			print(chunk)
			print()

		return True

# ============================================
# =           Exempt Handler Class           =
# ============================================
"""

	TODO:
	- Delete mentions from before 6 months ago

"""

class ExemptHandler(object):
	def __init__(self):
		self.service = self.g_auth()
		self.whitelist = self.get_whitelist()

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

	# -----------  Get Whitelist  -----------
	def get_whitelist(self):
		service = self.service
		values = self.get_category_users('whitelist')
		whitelist = []

		for value in values:
			if value == []:
				continue
			whitelist.append(value[0])

		if not values:
			return False
		else:
			return whitelist

	# -----------  Get screen_names from specific category  -----------
	def get_category_users(self, category):
		service = self.service
		RANGE_NAME = category.upper() + '!A2:A'

		result = service.spreadsheets().values().get(
			spreadsheetId=SPREADSHEET_ID,
			range=RANGE_NAME
		).execute()
		values = result.get('values', [])

		if not values:
			return False
		else:
			return values

	# -----------  Add User to Category Spreadsheet  -----------
	def add_users_to_category(self, category, screen_names):
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
	- Add tweets with > 100 interactions to whitelist
	- Add users in private Twitter lists to whitelist
	- Check if whitelist user follows me

"""

class Tweeder(object):
	def __init__(self, tw, sheet):
		self.tw = tw
		self.sheet = sheet

	# -----------  Add users who have interacted to their category sheets  -----------
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
					sheet.add_users_to_category(action, [[uscreen_name]])
					time.sleep(random.randrange(1, 4) * 2)

	# -----------  Add sheet category users to a twitter list  -----------
	def add_sheet_category_users_to_tw_list(self, category, list_id, list_slug, owner_screen_name):
		tw = self.tw
		sheet = self.sheet

		screen_names = sheet.get_category_users(category)
		tw.add_users_to_list(screen_names, list_id, list_slug, owner_screen_name)

		return True

	# -----------  Add user to category based off twitter information  -----------
	def add_tw_user_to_sheet_category(self, user):
		tw = self.tw
		sheet = self.sheet

		uscreen_name = user["screen_name"].lower()

		# Verified users (I know, I know)
		if user["verified"] == True:
			sheet.add_users_to_category('verified', [[uscreen_name]])
			return True

		# Users I have notifications on
		if user["notifications"] == True:
			sheet.add_users_to_category('notifications', [[uscreen_name]])
			return True

		return False

	# -----------  View whitelisted users  -----------
	def view_whitelisted_users(self):
		tw = self.tw
		sheet = self.sheet

		whitelist = sheet.get_whitelist()
		for screen_name in whitelist:
			print(screen_name)

	# -----------  Check if user is in whitelist  -----------
	def user_is_whitelisted(self, screen_name):
		sheet = self.sheet

		if screen_name in sheet.whitelist:
			return True
		return False

	# -----------  Compare following list to whitelist  -----------
	def unfollow_inactive_users(self):
		tw = self.tw
		sheet = self.sheet

		friends = tw.friends
		if friends == []:
			print('Friends are empty.  Retrieving new friends list...')
			friends = tw.get_twitter_friends()

		for friend in friends["users"]:
			screen_name = friend['screen_name']
			newly_whitelisted = self.add_tw_user_to_sheet_category(friend)
			if self.user_is_whitelisted(screen_name) or newly_whitelisted:
				print(STARTC + screen_name + ' is whitelisted.' + ENDC)
				continue
			else:
				unfollowed = tw.unfollow_twitter_user(friends[friend])
				print('Unfollowed ' + screen_name)
				print(unfollowed)
				print()
				time.sleep(random.randrange(1, 4) * 2)


# ======================================
# =           Helper Options           =
# ======================================

def menu():
	user_options = [
		"View whitelisted users",
		"Delete tweets older than 2 years",
		"Delete tweets without interactions",
		"Unfollow users",
		"Add recent interactions to whitelist",
		"test",
	]

	opts = Picker(
		title = 'What would you like to do?',
		options = user_options
	).getSelected()

	for opt in opts:
		if opt == user_options[0]:
			tweeder.view_whitelisted_users()
		elif opt == user_options[1]:
			tw.delete_archived_tweets()
		elif opt == user_options[2]:
			tw.delete_tweets_without_interactions()
		elif opt == user_options[3]:
			tweeder.unfollow_inactive_users()
		elif opt == user_options[4]:
			tweeder.add_recent_interactions_to_whitelist()
		elif opt == user_options[5]:
			print("Test successful.")

	answ = input("Would you like to do more? (Y/N) ")
	if answ.lower() in ('n', 'no', 'exit', 'quit', 'q'):
		return False

	return True

def main():
	tw = AccountHandler()
	sheet = ExemptHandler()
	tweeder = Tweeder(tw, sheet)

	running = True
	while running:
		running = menu()

	print("Thank you, come again!")
	return

if __name__ == '__main__':
	main()
