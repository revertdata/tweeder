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
from oauth2client.service_account import ServiceAccountCredentials
from urllib.request import urlopen, HTTPError

import sys
import re
import json
import random

from twitter import *
from t import ACCESS_TOKEN_KEY, ACCESS_TOKEN_SECRET, CONSUMER_KEY, CONSUMER_SECRET

import gspread
from googleapiclient.discovery import build
from g import SCOPES, SPREADSHEET_ID, GSPREAD_SCOPES

STARTC='\033[90m'
ENDC='\033[0m'
utc=pytz.UTC

# =============================================
# =           Account Handler Class           =
# =============================================

class AccountHandler(object):
	def __init__(self):
		self.t = Twitter(auth=OAuth(ACCESS_TOKEN_KEY, ACCESS_TOKEN_SECRET, CONSUMER_KEY, CONSUMER_SECRET))
		self.feed = []
		self.friends = []

	# -----------  Get Recent Tweets -----------
	def get_recent_tweets(self, uscreen_name):
		t = self.t
		feed = t.statuses.user_timeline(screen_name=uscreen_name, count=200, exclude_replies=True, trim_user=True)

		self.feed = feed
		return feed

	# -----------  Get Twitter Followers  -----------
	def get_twitter_friends(self, cursor):
		t = self.t
		friends = t.friends.list(count=200, skip_status=True, include_user_entities=False, cursor=cursor)

		self.friends = friends
		return friends

	# -----------  Get Twitter Lists  -----------
	def get_twitter_lists(self, uscreen_name):
		t = self.t
		owned_lists = t.lists.ownerships(count=25, screen_name=uscreen_name)["lists"]

		return owned_lists

	# -----------  Get List Members  -----------
	def get_twitter_list_members(self, list_id):
		t = self.t
		screen_names = t.lists.members(list_id=list_id, count=5000, include_entities=False, skip_status=True)

		return screen_names

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
		old_tweets = []

		with open('tweet.json', 'r') as tweets:
			tweetlist = json.load(tweets)
			for tweet in tweetlist:
				tweet = tweet["tweet"]
				try:
					created_at = datetime.strptime(tweet["created_at"],"%a %b %d %H:%M:%S %z %Y")
					old_enough = created_at.replace(tzinfo=utc) < past_time.replace(tzinfo=utc)
					if old_enough:
						old_tweets.append(tweet)
				except Exception as e:
					print()
					print("-----------")
					print()
					print("ERROR in AccountHandler.get_old_tweets:")
					print(STARTC)
					print(e)
					print(ENDC)
					print("-----------")
					continue
		return old_tweets, created_at

	# -----------  Delete tweets older than 2 years  -----------
	def delete_archived_tweets(self):
		t = self.t
		old_tweets, created_at = self.get_old_tweets(2)

		for tweet in old_tweets:
			try:
				t.statuses.destroy(_id=tweet['id_str'])
				print(tweet['full_text'])
				print('DELETED ' + tweet['id_str'] + ' (' + created_at.strftime("%a %b %d %H:%M:%S %z %Y") + ')')
				print()
			except Exception as e:
					print()
					print("-----------")
					print()
					print("ERROR in AccountHandler.get_old_tweets:")
					print(STARTC)
					print(e)
					print(ENDC)
					print("-----------")

		return True

	# -----------  Delete tweets without interactions  -----------
	def delete_tweets_without_interactions(self):
		t = self.t
		old_tweets, created_at = self.get_old_tweets(0)

		for tweet in old_tweets:
			try:
				# check if there are interactions
				interactions = int(tweet["favorite_count"])+int(tweet["retweet_count"])
				if interactions == 0:
					t.statuses.destroy(_id=tweet["id_str"])
					print(tweet['full_text'] + ' (' + str(interactions) + ' interactions) ')
					print('DELETED ' + tweet['id_str'] + ' (' + created_at.strftime("%a %b %d %H:%M:%S %z %Y") + ')')
					print()
			except Exception as e:
					print()
					print("-----------")
					print()
					print("ERROR in AccountHandler.get_old_tweets:")
					print(STARTC)
					print(e)
					print(ENDC)
					print("-----------")

		return True

	# -----------  Unfollow users on Twitter  -----------
	def unfollow_twitter_user(self, uscreen_name):
		t = self.t
		t.friendships.destroy(screen_name=uscreen_name)

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
		self.service, self.client = self.g_auth()
		self.whitelist = self.get_whitelist()
		self.categories = ['MENTIONS', 'FAVORITED', 'RETWEETED', 'VERIFIED', 'NOTIFICATIONS', 'LISTED', 'TWEETS']

		return

	# -----------  Basic Google Authentication  -----------
	def g_auth(self):
		store = file.Storage('token.json')
		creds = store.get()
		if not creds or creds.invalid:
			flow = client.flow_from_clientsecrets('credentials.json', SCOPES)
			creds = tools.run_flow(flow, store)
		service = build('sheets', 'v4', http=creds.authorize(Http()))

		gcreds = ServiceAccountCredentials.from_json_keyfile_name('service_credentials.json', GSPREAD_SCOPES)
		client = gspread.authorize(gcreds)

		return service, client

	# -----------  Get Whitelist  -----------
	def get_whitelist(self):
		service = self.service
		values = self.get_category_users('whitelist')

		return values

	# -----------  Get screen_names from specific category  -----------
	def get_category_users(self, category):
		service = self.service
		RANGE_NAME = category.upper() + '!A2:A'

		result = service.spreadsheets().values().get(
			spreadsheetId=SPREADSHEET_ID,
			range=RANGE_NAME
		).execute()
		values = result.get('values', [])

		cat_users = []

		for value in values:
			if value == []:
				continue
			cat_users.append(value[0])

		if not values:
			return False
		else:
			return cat_users

	# -----------  Get single cell value  -----------
	def get_cell_value(self, category, range):
		service = self.service
		RANGE_NAME = category.upper()+'!'+str(range)

		result = service.spreadsheets().values().get(
			spreadsheetId=SPREADSHEET_ID,
			range=RANGE_NAME
		).execute()
		values = result.get('values', [])

		if not values:
			return False
		else:
			return values[0][0]

	# -----------  Get next Twitter API cursor -----------
	def get_next_cursor(self):

		return self.get_cell_value('cursor', 'A2')

	# -----------  Get cleanup_cursor  -----------
	def get_cleanup_cursor(self):

		return self.get_cell_value('cursor', 'A3')

	# -----------  Overwrite cell in spreadsheet  -----------
	def overwrite_cell(self, value, category, range):
		service = self.service
		client = self.client

		resource = {"values": [[value]]}
		CAT_RANGE = category.upper()+"!"+range;

		# delete old cursor
		service.spreadsheets().values().clear(
			spreadsheetId=SPREADSHEET_ID,
			range=CAT_RANGE,
		).execute()

		# overwrite
		service.spreadsheets().values().append(
			spreadsheetId=SPREADSHEET_ID,
			range=CAT_RANGE,
			body=resource,
			valueInputOption="USER_ENTERED"
		).execute()

		return

	# -----------  Replace next twitter API cursor  -----------
	def overwrite_next_cursor(self, next_cursor):

		return self.overwrite_cell(next_cursor, 'cursor', 'A2')

	# -----------  Replace next whitelist cleanup cursor  -----------
	def overwrite_cleanup_cursor(self, uscreen_name):

		return self.overwrite_cell(uscreen_name, 'cursor', 'A3')

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

	# -----------  Remove User from Category Spreadsheet  -----------
	def remove_user_from_category(self, category, uscreen_name):
		service = self.service
		removed = False

		category_users = self.get_category_users(category)
		if category_users and uscreen_name in category_users:
			rows_to_remove = category_users.count(uscreen_name)
			for x in range(rows_to_remove):
				category_users = self.get_category_users(category)
				row_index = category_users.index(uscreen_name)
				self.remove_row_from_category_spreadsheet(category, row_index+2)
				removed = True

		if removed:
			print(STARTC+"Removed "+uscreen_name+" from "+category+ENDC)

		return True

	# -----------  Remove row from Category Spreadsheet  -----------
	def remove_row_from_category_spreadsheet(self, category, row_index):
		service = self.service
		client = self.client

		sheet = client.open("Twitter mentions").worksheet(category.upper())
		print(sheet.row_values(row_index))
		deleted = sheet.delete_row(row_index)

		return deleted

	# -----------  Delete old dates from MENTIONS Spreadsheet  -----------
	def remove_old_mentions(self):
		service = self.service
		MENTIONS_DATE_COL = "MENTIONS!C2:C"

		result = service.spreadsheets().values().get(
			spreadsheetId=SPREADSHEET_ID,
			range=MENTIONS_DATE_COL
		).execute()
		values = result.get('values', [])

		if not values:
			return False
		else:
			screen_names = []
			past_time = datetime.now() - relativedelta(months=6)
			print('Deleting mentions older than ' + str(past_time.replace(tzinfo=utc)) + '...')
			row_index = 2 # row_index is offset by 2 in Google Sheets
			for datecol in values:
				if datetime.strptime(datecol[0],"%m/%d/%Y").replace(tzinfo=utc) < past_time.replace(tzinfo=utc):
					screen_names.append(self.get_cell_value('mentions', 'A'+str(row_index)))
					self.remove_row_from_category_spreadsheet('mentions', row_index)
				else:
					# only increase the row_index if you didn't delete a row
					row_index += 1

			return screen_names

		return True

	# -----------  Delete old mentions from users who appear multiple times  -----------
	def remove_old_duplicate_mentions(self):
		service = self.service
		MENTIONS_USCREEN_COL = "MENTIONS!A2:A"

		result = service.spreadsheets().values().get(
			spreadsheetId=SPREADSHEET_ID,
			range=MENTIONS_USCREEN_COL
		).execute()
		values = result.get('values', [])

		if not values:
			return False
		else:
			screen_names = []
			row_index = 2 # row_index is offset by 2 in Google Sheets
			for index, uscreen_name in enumerate(values):
				# sleepy first to display the deletion after username
				sleepy = random.randrange(1, 4) * 2
				_x = sleepy
				for _ in range(sleepy+1):
					print('\r0{0} {1}'.format(_x, uscreen_name[0]).ljust(30)+'\r', end='', flush=True)
					_x -= 1
					time.sleep(1)

				if values[index+1:].count(uscreen_name) > 0:
					screen_names.append(self.get_cell_value('mentions', 'A'+str(row_index)))
					self.remove_row_from_category_spreadsheet('mentions', row_index)

				else:
					# only increase the row_index if you didn't delete a row
					row_index += 1

			return screen_names

		return True

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
					user = t.users.show(user_id=uid)
					uscreen_name = user['screen_name'].lower()
					sheet.add_users_to_category(action, [[uscreen_name]])
					sleepy = random.randrange(1, 4) * 2
					_x = sleepy
					for _ in range(sleepy+1):
						print('\r0{0} {1}'.format(_x, uscreen_name).ljust(30)+'\r', end='', flush=True)
						_x -= 1
						time.sleep(1)

	# -----------  Add sheet category users to a twitter list  -----------
	def add_sheet_category_users_to_tw_list(self, category, list_id, list_slug, owner_screen_name):
		tw = self.tw
		sheet = self.sheet

		screen_names = sheet.get_category_users(category)
		tw.add_users_to_list(screen_names, list_id, list_slug, owner_screen_name)

		return True

	# -----------  Add user to category based off twitter information  -----------
	def add_tw_user_to_sheet_category(self, uscreen_name):
		tw = self.tw
		sheet = self.sheet

		# Verified users (I know, I know)
		if user["verified"] == True:
			sheet.add_users_to_category('verified', [[uscreen_name]])
			return True

		# Users I have notifications on
		if user["notifications"] == True:
			sheet.add_users_to_category('notifications', [[uscreen_name]])
			return True

		return False

	# -----------  Add listed users to whitelist  -----------
	def add_listed_users_to_whitelist(self, owner_screen_name):
		tw = self.tw
		sheet = self.sheet

		lists = tw.get_twitter_lists(owner_screen_name)
		for li in lists:
			members = tw.get_twitter_list_members(li["id"])
			print("Adding users from '"+li["name"])
			for user in members["users"]:
				uscreen_name = user['screen_name'].lower()
				sheet.add_users_to_category('listed', [[uscreen_name]])
				sleepy = random.randrange(1, 4) * 2
				_x = sleepy
				for _ in range(sleepy+1):
					print('\r0{0} {1}'.format(_x, uscreen_name).ljust(30)+'\r', end='', flush=True)
					_x -= 1
					time.sleep(1)

	# -----------  View whitelisted users  -----------
	def view_whitelisted_users(self):
		tw = self.tw
		sheet = self.sheet

		whitelist = sheet.get_whitelist()
		for screen_name in whitelist:
			print(screen_name)

	# -----------  Check if user is in whitelist  -----------
	def user_is_whitelisted(self, uscreen_name):
		sheet = self.sheet

		if uscreen_name in sheet.whitelist:
			return True
		return False

	# -----------  Compare following list to whitelist  -----------
	def unfollow_inactive_users(self):
		tw = self.tw
		sheet = self.sheet

		friends = tw.friends
		next_cursor = sheet.get_next_cursor()
		if friends == []:
			friends = tw.get_twitter_friends(next_cursor)

		whitelisted = 0
		for friend in friends['users']:
			uscreen_name = friend['screen_name'].lower()
			try:
				if self.user_is_whitelisted(uscreen_name):
					print(STARTC + uscreen_name + ' is whitelisted.' + ENDC)
					whitelisted += 1
					continue
				else:
					self.unfollow_after_newly_whitelisted_check(uscreen_name)

			except Exception as e:
				print()
				print("-----------")
				print("ERROR in Tweeder.unfollow_inactive_users:")
				print(STARTC)
				print(e)
				print(ENDC)
				print("-----------")
				continue
			sleepy = random.randrange(1, 4) * 2
			_x = sleepy
			for _ in range(sleepy+1):
				print('\r0{0} {1}'.format(_x, uscreen_name).ljust(30)+'\r', end='', flush=True)
				_x -= 1
				time.sleep(1)

		if whitelisted == len(friends['users']):
			next_cursor = friends['next_cursor']
			if (friends['next_cursor'] == 0):
				next_cursor = -1
			sheet.overwrite_next_cursor(next_cursor)
			print("Everyone in this batch has been whitelisted. NEXT CURSOR overwritten: "+str(next_cursor))

	# -----------  Check if user is "newly whitelisted", determine unfollow  -----------
	def unfollow_after_newly_whitelisted_check(self, uscreen_name):
		newly_whitelisted = self.add_tw_user_to_sheet_category(uscreen_name)
		if newly_whitelisted:
			print(STARTC + uscreen_name + ' is newly whitelisted.' + ENDC)
			return False
		else:
			unfollowed = tw.unfollow_twitter_user(uscreen_name)
			print('Unfollowed ' + uscreen_name)

		return True

	# -----------  Remove users from categories if not following  -----------
	def remove_unfollowers_from_categories(self, source_screen_name):
		tw = self.tw
		sheet = self.sheet

		categories = sheet.categories
		whitelist = sheet.get_whitelist()
		cleanup_cursor = sheet.get_cleanup_cursor()

		if cleanup_cursor in whitelist:
			cleanup_cursor = cleanup_cursor.lower()
			whitelist = whitelist[whitelist.index(cleanup_cursor):]
		elif cleanup_cursor != False:
			start_at_letter = [i for i in whitelist if i.startswith(cleanup_cursor[0][0])][0]
			whitelist = whitelist[whitelist.index(start_at_letter):]

		max_requests = 150
		for screen_name in whitelist:
			uscreen_name = screen_name.strip().lower()
			try:
				friendship = tw.t.friendships.show(source_screen_name=source_screen_name, target_screen_name=uscreen_name)
				max_requests -= 1

				if friendship["relationship"]["target"]["following"] == False:
					print(STARTC + uscreen_name + " is not following." + ENDC)
					for category in categories:
						sheet.remove_user_from_category(category, uscreen_name)
				elif friendship["relationship"]["target"]["followed_by"] == False:
					print(STARTC + uscreen_name + " is a new Reply Guy!" + ENDC)
					tw.t.friendships.create(screen_name=uscreen_name, follow=False)
					tw.t.friendships.update(screen_name=uscreen_name, retweets=False)
				else:
					tw.t.friendships.update(screen_name=uscreen_name, retweets=False)

				if max_requests <= 0:
					print('MAX_REQUESTS Limit reached.  Please wait 5 minutes to try again ('+str(datetime.now()+relativedelta(minutes=15))+').')
					sleepy = 300 # 5 minutes
					_x = sleepy
					max_requests = 150
					for _ in range(sleepy+1):
						print('\r0{0} {1}'.format(_x, uscreen_name).ljust(30)+'\r', end='', flush=True)
						_x -= 1
						time.sleep(1)
			except Exception as e:
				print()
				print("-----------")
				print("ERROR in Tweeder.remove_unfollowers_from_categories:")
				print(STARTC)
				print(e)
				print(ENDC)
				print("-----------")
				continue

			sheet.overwrite_cleanup_cursor(uscreen_name)
			sleepy = random.randrange(1, 4) * 2
			_x = sleepy
			for _ in range(sleepy+1):
				print('\r0{0} {1}'.format(_x, uscreen_name).ljust(30)+'\r', end='', flush=True)
				_x -= 1
				time.sleep(1)

	# -----------  Daily Tasks  -----------
	def dailies(self):
		tw = self.tw
		sheet = self.sheet

		# Reset CURSORs
		sheet.overwrite_next_cursor('-1')
		sheet.overwrite_cleanup_cursor('')

		# Remove old mentions
		removed_users = list(set(sheet.remove_old_mentions()))
		for screen_name in removed_users:
			uscreen_name = screen_name.lower()
			if not self.user_is_whitelisted(uscreen_name):
				print(STARTC + uscreen_name + ' has not tweeted at you in 6 months.' + ENDC)
				_unfollowed = self.unfollow_after_newly_whitelisted_check(uscreen_name)

		# Unfollow inactive users
		self.remove_unfollowers_from_categories('telepathics')

# ======================================
# =           Helper Options           =
# ======================================

def menu():
	user_options = [
		"Daily tasks",
		"Delete tweets older than 2 years",
		"Delete tweets without interactions",
		"Unfollow users",
		"Add recent interactions to whitelist",
		"Add listed users to whitelist",
		"Remove mentions > 6 months",
		"Clean category users",
		"Reset CURSORs",
		"Remove duplicate mentions"
	]

	opts = Picker(
		title = 'What would you like to do?',
		options = user_options
	).getSelected()

	# ===== CONNECT TO RESOURCES AND CLASSES =====
	_tw = AccountHandler()
	_sheet = ExemptHandler()
	tweeder = Tweeder(_tw, _sheet)
	# ===== CONNECTION COMPLETE =====

	if opts == False:
		return opts

	for opt in opts:
		if opt == user_options[0]:
			tweeder.dailies()
		elif opt == user_options[1]:
			tweeder.tw.delete_archived_tweets()
		elif opt == user_options[2]:
			tweeder.tw.delete_tweets_without_interactions()
		elif opt == user_options[3]:
			tweeder.unfollow_inactive_users()
		elif opt == user_options[4]:
			tweeder.add_recent_interactions_to_whitelist()
		elif opt == user_options[5]:
			tweeder.add_listed_users_to_whitelist('telepathics')
		elif opt == user_options[6]:
			# TODO check if user is in whitelist after removal, unfollow if not
			tweeder.sheet.remove_old_mentions()
		elif opt == user_options[7]:
			tweeder.remove_unfollowers_from_categories('telepathics')
		elif opt == user_options[8]:
			tweeder.sheet.overwrite_next_cursor('-1')
			tweeder.sheet.overwrite_cleanup_cursor('')
		elif opt == user_options[9]:
			removed_users = tweeder.sheet.remove_old_duplicate_mentions()
			print(removed_users)
		else:
			return True

	answ = input("Would you like to do more? (Y/N) ")
	if answ.lower() in ('no', 'n', 'exit', 'e', 'quit', 'q'):
		return False

	return True

def main():
	running = True
	while running:
		running = menu()

	print("Thank you, come again!")
	return

if __name__ == '__main__':
	main()
