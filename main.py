#!/usr/bin/env python3

# =======================================
# =           Twitter cleaner           =
# =   https://twitter.com/telepathics   =
# =======================================

import time
import pytz
from datetime import datetime, timezone
from dateutil.relativedelta import relativedelta

from picker import Picker
from httplib2 import Http
from oauth2client import file, client, tools
from oauth2client.service_account import ServiceAccountCredentials
from urllib.request import urlopen, HTTPError

import sys
import re
import json
import random

from twitter import Twitter, OAuth
from t import ACCESS_TOKEN_KEY, ACCESS_TOKEN_SECRET, CONSUMER_KEY, CONSUMER_SECRET, MIN_FAVS, AUTH_SCREEN_NAME, DM_MSG

import gspread
from googleapiclient.discovery import build
from g import SHEET_NAME, ROW_OFFSET, SCOPES, SPREADSHEET_ID, GSPREAD_SCOPES

STARTC='\033[90m'
ENDC='\033[0m'
utc=pytz.UTC
SHEET_LINK = 'https://docs.google.com/spreadsheets/d/'+SPREADSHEET_ID+'/edit#gid=0'
CANCEL_OPTIONS = ('no', 'n', 'exit', 'e', 'quit', 'q')

# =============================================
# =          Public Helper Functions          =
# =============================================

def sleep_overlay(prev_text='', sleepy=random.randrange(1,8)):
	_x = sleepy
	for _ in range(sleepy+1):
		print('\r0{0} {1}'.format(_x, prev_text).ljust(30)+'\r', end='', flush=True)
		_x -= 1
		time.sleep(1)

	return True

def display_error(e, location):
	print("\n-----------\n")
	print("ERROR in " + location + ":")
	print(STARTC)
	print(e)
	print("\n" + SHEET_LINK + ENDC)
	print("\n-----------\n")

	return

def max_request_limit_warning(sleepy):

	return sleep_overlay(STARTC + 'MAX_REQUEST Limit reached.  Please wait...' + ENDC, sleepy)

# =============================================
# =           Account Handler Class           =
# =============================================

class AccountHandler(object):
	def __init__(self):
		self.t = Twitter(auth=OAuth(ACCESS_TOKEN_KEY, ACCESS_TOKEN_SECRET, CONSUMER_KEY, CONSUMER_SECRET))
		self.feed = []
		self.friends = []
		self.resources = self.t.application.rate_limit_status()['resources']

	# -----------  Check Rate Limit  -----------
	def check_rate_limit(self):
		t = self.t
		resources = self.resources
		reset_time = self.resources['application']['/application/rate_limit_status']['reset']
		curr_epoch = int(time.time())
		if reset_time < curr_epoch:
			resources = t.application.rate_limit_status()['resources']
			self.resources = resources

		return resources

	# -----------  Update Rate Limit  -----------
	def update_t_rate_limit(self, resource, path, minus_remaining=1):
		rate_limit = self.check_rate_limit()[resource][path]
		warning_complete = False
		while rate_limit['remaining'] <= 1 and warning_complete != True:
			warning_complete = max_request_limit_warning(int(time.time()) - rate_limit['reset'])

		return warning_complete

	# -----------  Get Twitter Followers  -----------
	def get_twitter_friends(self, cursor):
		t = self.t

		friends = t.friends.list(count=200, skip_status=True, include_user_entities=False, cursor=cursor)
		self.update_t_rate_limit('friends', '/friends/list')
		self.friends = friends

		return friends

	# -----------  Get Twitter Lists  -----------
	def get_twitter_lists(self, uscreen_name):
		t = self.t

		owned_lists = t.lists.ownerships(count=25, screen_name=uscreen_name)["lists"]
		self.update_t_rate_limit('lists', '/lists/ownerships')

		return owned_lists

	# -----------  Get List Members  -----------
	def get_twitter_list_members(self, list_id):
		t = self.t

		screen_names = t.lists.members(list_id=list_id, count=5000, include_entities=False, skip_status=True)
		self.update_t_rate_limit('lists', '/lists/members')

		return screen_names

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
					display_error(e, 'AccountHandler.get_old_tweets')
					continue
		return old_tweets, created_at

	# -----------  Send DM  -----------
	def send_direct_message(self, uscreen_name):
		t = self.t

		sent = t.direct_messages.events.new(
			_json={
				"event": {
					"type": "message_create",
					"message_create": {
						"target": {
								"recipient_id": t.users.show(screen_name=uscreen_name)["id"]},
						"message_data": {
								"text": DM_MSG}
					}
				}
			}
		)
		self.update_t_rate_limit('direct_messages', '/direct_messages/sent_and_received')

		return sent

	# -----------  Delete tweets older than 2 years  -----------
	def delete_archived_tweets(self):
		t = self.t
		old_tweets, created_at = self.get_old_tweets(2)

		for tweet in old_tweets:
			if int(tweet['favorite_count']) < MIN_FAVS:
				try:
					t.statuses.destroy(_id=tweet['id_str'])
					print(tweet['full_text'])
					print('DELETED ' + tweet['id_str'] + ' (' + created_at.strftime("%a %b %d %H:%M:%S %z %Y") + ')')
					print('* ' + tweet['favorite_count'] + ' favorites\n')
					# TODO figure out more accurate rate limit
					sleep_overlay(STARTC + 'Looking for next archived tweet...' + ENDC)

				except Exception as e:
					display_error(e, 'AccountHandler.delete_archived_tweets')
					continue
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
					print('DELETED ' + tweet['id_str'] + ' (' + created_at.strftime("%a %b %d %H:%M:%S %z %Y") + ')\n')
					# TODO figure out more accurate rate limit
					sleep_overlay(STARTC + 'Looking for next tweet...' + ENDC)
			except Exception as e:
					display_error(e, 'AccountHandler.delete_tweets_without_interactions')
					continue

		return True

	# -----------  Unfollow users on Twitter  -----------
	def unfollow_twitter_user(self, uscreen_name):
		t = self.t

		user = t.users.show(screen_name=uscreen_name)
		self.update_t_rate_limit('users', '/users/show/:id')

		if user["protected"] == False and user["following"] == True:
			t.friendships.destroy(screen_name=uscreen_name)
			# TODO figure out more accurate rate limit
			sleep_overlay(STARTC + 'unfollowing ' + uscreen_name + ENDC)
			return True
		else:
			no_unfollow_msg = ''
			if user["following"] == True:
				no_unfollow_msg += 'Didn\'t unfollow https://twitter.com/' + uscreen_name
				if user["protected"] == True:
					no_unfollow_msg += STARTC + ' [user is protected]' + ENDC
				print(no_unfollow_msg)
			return False

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
			# TODO figure out more accurate rate limit
			sleep_overlay(STARTC + 'Loading...' + ENDC)
			print("Added the following users to the list '" + list_slug + "'.")
			print(chunk)

		return True

# ============================================
# =           Exempt Handler Class           =
# ============================================

class ExemptHandler(object):
	def __init__(self, reset):
		self.rate_limit = {
			# sheets api: 100 requests/100 seconds/1 user
			"limit": 100,
			"remaining": 100,
			"reset": reset
		}

		self.service, self.sheet = self.g_auth()
		self.whitelist = self.get_category_users('whitelist')
		self.categories = ['MENTIONS', 'LISTED']

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
		gclient = gspread.authorize(gcreds)
		sheet = gclient.open(SHEET_NAME)

		return service, sheet

	# -----------  Reset Rate Limit  -----------
	def reset_g_rate_limit(self):
		rate_limit = {
			"limit": 100,
			"remaining": 100,
			"reset": time.time()
		}
		self.rate_limit = rate_limit

		return rate_limit

	# -----------  Update Rate Limit  -----------
	def update_g_rate_limit(self, minus_remaining=1):
		rate_limit = self.rate_limit
		time_left = 100 + rate_limit['reset'] - time.time()
		if rate_limit['remaining'] <= 1 and time_left <= 0:
			max_request_limit_warning(100)
			self.reset_g_rate_limit()
		else:
			self.rate_limit['remaining'] -= minus_remaining

		return

	# -----------  Get screen_names from specific category  -----------
	def get_category_users(self, category, col='A'):
		service = self.service
		RANGE_NAME = category.upper() + '!' + col + '2:' + col

		result = service.spreadsheets().values().get(
			spreadsheetId=SPREADSHEET_ID,
			range=RANGE_NAME
		).execute()
		self.update_g_rate_limit()
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
		self.update_g_rate_limit()
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

	# -----------  Get duplicate_cursor  -----------
	def get_duplicate_cursor(self):

		return self.get_cell_value('cursor', 'A4')

	# -----------  Overwrite cell in spreadsheet  -----------
	def overwrite_cell(self, value, category, range):
		service = self.service
		resource = {"values": [[value]]}
		CAT_RANGE = category.upper()+"!"+range

		# delete old cursor
		service.spreadsheets().values().clear(
			spreadsheetId=SPREADSHEET_ID,
			range=CAT_RANGE,
		).execute()
		self.update_g_rate_limit()

		# overwrite
		service.spreadsheets().values().append(
			spreadsheetId=SPREADSHEET_ID,
			range=CAT_RANGE,
			body=resource,
			valueInputOption="USER_ENTERED"
		).execute()
		self.update_g_rate_limit()

		return

	# -----------  Replace next twitter API cursor  -----------
	def overwrite_next_cursor(self, next_cursor):

		return self.overwrite_cell(next_cursor, 'cursor', 'A2')

	# -----------  Replace next whitelist cleanup cursor  -----------
	def overwrite_cleanup_cursor(self, uscreen_name):

		return self.overwrite_cell(uscreen_name, 'cursor', 'A3')

	# -----------  Replace next mention cursor  -----------
	def overwrite_duplicate_cursor(self, uscreen_name):

		return self.overwrite_cell(uscreen_name, 'cursor', 'A4')

	# -----------  Add User to Category Spreadsheet  -----------
	def add_users_to_category(self, category, screen_names):
		service = self.service
		resource = {"values": screen_names}
		CAT_RANGE = category.upper() + "!A:A"

		service.spreadsheets().values().append(
			spreadsheetId=SPREADSHEET_ID,
			range=CAT_RANGE,
			body=resource,
			valueInputOption="USER_ENTERED"
		).execute()
		self.update_g_rate_limit()

		return

	# -----------  Remove User from Category Spreadsheet  -----------
	def remove_user_from_category(self, category, uscreen_name):
		removed = False
		category_users = self.get_category_users(category)

		if category_users and uscreen_name in category_users:
			rows_to_remove = category_users.count(uscreen_name)
			for _ in range(rows_to_remove):
				category_users = self.get_category_users(category)
				row_index = category_users.index(uscreen_name)
				self.remove_row_from_category_spreadsheet(category, row_index + ROW_OFFSET)
				removed = True

		if removed:
			print(STARTC + "Removed " + uscreen_name + " from " + category + ENDC)

		return True

	# -----------  Remove row from Category Spreadsheet  -----------
	def remove_row_from_category_spreadsheet(self, category, row_index):
		spreadsheet = self.sheet.worksheet(category.upper())

		deleted = spreadsheet.delete_row(row_index)
		self.update_g_rate_limit()

		return deleted

	# -----------  Delete old dates from MENTIONS Spreadsheet  -----------
	def remove_old_mentions(self):
		service = self.service
		dm_list = self.get_category_users('DM', 'B')
		MENTIONS_DATE_COL = "MENTIONS!C2:C"

		result = service.spreadsheets().values().get(
			spreadsheetId=SPREADSHEET_ID,
			range=MENTIONS_DATE_COL
		).execute()
		self.update_g_rate_limit()
		values = result.get('values', [])

		if not values:
			return False
		else:
			dm_screen_names = []
			removed_screen_names = []
			past_time = (datetime.now() - relativedelta(months=6)).replace(tzinfo=utc)
			up_next_end = (datetime.now() - relativedelta(months=6) + relativedelta(days=7)).replace(tzinfo=utc)
			last_week = (datetime.now() - relativedelta(days=6)).replace(tzinfo=utc)
			row_index = 0 + ROW_OFFSET

			print('Deleting mentions older than ' + str(past_time) + '...')

			# double-check IFTTT applet is running (if there have been mentions in the last 7 days)
			cont = True
			recent_mentions = False
			for datecol in values:
				udatetime = datetime.strptime(datecol[0],"%m/%d/%Y").replace(tzinfo=utc)
				if udatetime > last_week:
					recent_mentions = True
			if not recent_mentions:
				print('Please double-check that IFTTT is running the applet.')
				answ = input('Continue? (Y/N): ')
				if answ.lower() in CANCEL_OPTIONS:
					cont = False

			if cont == True:
				for datecol in values:
					uscreen_name = self.get_cell_value('mentions', 'A'+str(row_index)).lower()
					udatetime = datetime.strptime(datecol[0],"%m/%d/%Y").replace(tzinfo=utc)
					if udatetime < past_time:
						removed_screen_names.append(uscreen_name)
						if self.get_cell_value('mentions', 'D' + str(row_index)) != 'error':
							self.remove_row_from_category_spreadsheet('mentions', row_index)
					else:
						row_index += 1
						# check if user submitted grace-period entry
						if udatetime < up_next_end and uscreen_name in dm_list:
							dm_screen_names.append(uscreen_name)
						else:
							break

				return [removed_screen_names, dm_screen_names]
			return False
		return True

	# -----------  Delete old mentions from users who appear multiple times  -----------
	def remove_old_duplicate_category(self, category):
		values = self.get_category_users(category.lower())
		listed = self.get_category_users('listed')

		if not values:
			return False
		else:
			print('Cleaning up duplicate ' + category + '...')

			row_index = 0 + ROW_OFFSET
			duplicate_cursor = self.get_duplicate_cursor()
			if duplicate_cursor in values:
				row_index = values.index(duplicate_cursor) + ROW_OFFSET
				values = values[values.index(duplicate_cursor):]

			removed_screen_names = []
			for index, uscreen_name in enumerate(values):
				# remove user from mentions sheets if listed or repeated
				user_listed = category.lower() == 'mentions' and uscreen_name in listed
				if user_listed or (values[index+1:].count(uscreen_name) > 0):
					removed_screen_names.append(self.get_cell_value(category.lower(), 'A'+str(row_index)))
					self.remove_row_from_category_spreadsheet(category.lower(), row_index)
				else:
					row_index += 1
					self.overwrite_duplicate_cursor(uscreen_name)

				sleep_overlay(STARTC + uscreen_name + ENDC)

			return removed_screen_names

		return True

# =========================================
# =           Tweeder Functions           =
# =========================================

class Tweeder(object):
	def __init__(self, tw, sheet):
		self.tw = tw
		self.sheet = sheet

		return

	# -----------  reset cursors -----------
	def reset_cursors(self):
		sheet = self.sheet

		sheet.overwrite_next_cursor('-1')
		sheet.overwrite_cleanup_cursor('')
		sheet.overwrite_duplicate_cursor('')

		return

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

		t = tw.t
		user = t.users.show(screen_name=uscreen_name)

		# check if user should be listed
		if user["verified"] == True or user["notifications"] == True:
			sheet.add_users_to_category('listed', [[uscreen_name]])
			return True

		return False

	# -----------  Add listed users to whitelist  -----------
	def add_listed_users_to_whitelist(self, owner_screen_name):
		tw = self.tw
		sheet = self.sheet
		lists = tw.get_twitter_lists(owner_screen_name)
		listed = sheet.get_category_users('listed')

		for li in lists:
			members = tw.get_twitter_list_members(li["id"])
			answ = input("Add users from "+li["name"]+"? (Y/N): ")
			if answ.lower() not in CANCEL_OPTIONS:
				for user in members["users"]:
					uscreen_name = user['screen_name'].lower()
					if uscreen_name not in listed:
						followed_by = self.check_is_followed_by(uscreen_name)
						if followed_by:
							sheet.add_users_to_category('listed', [[uscreen_name]])
							sleep_overlay(uscreen_name)
						else:
							unfollowed = tw.unfollow_twitter_user(uscreen_name)
							if unfollowed == True:
								try:
									tw.t.lists.members.destroy(list_id=li["id"], screen_name=uscreen_name)
								except Exception as e:
									display_error(e, 'AccountHandler.unfollow_inactive_users')
									continue
		return

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

		whitelisted = []
		unfollowed_users = []
		running = True
		while running:
			for friend in friends['users']:
				uscreen_name = friend['screen_name'].lower()
				if uscreen_name not in whitelisted and uscreen_name not in unfollowed_users:
					try:
						if self.user_is_whitelisted(uscreen_name):
							print(STARTC + uscreen_name + ' is whitelisted.' + ENDC)
							whitelisted.append(uscreen_name)
							continue
						else:
							unfollowed = self.unfollow_after_newly_whitelisted_check(uscreen_name)
							if unfollowed == False:
								whitelisted.append(uscreen_name)
							else:
								unfollowed_users.append(uscreen_name)
					except Exception as e:
						display_error(e, 'AccountHandler.unfollow_inactive_users')
						continue

			if len(whitelisted) == len(friends['users']):
				next_cursor = friends['next_cursor']
				if (friends['next_cursor'] == 0):
					next_cursor = -1
					running = False
				sheet.overwrite_next_cursor(next_cursor)
				print("NEXT_CURSOR overwritten: "+str(next_cursor))
				# reset!
				friends = tw.get_twitter_friends(next_cursor)
				whitelisted = []
				unfollowed_users = []

		self.remove_unfollowers_from_categories()
		return

	# -----------  Check if user is following  -----------
	def check_is_followed_by(self, uscreen_name):
		tw = self.tw
		sheet = self.sheet

		categories = sheet.categories
		blocked_list = sheet.get_category_users('blocked')
		manual_list = sheet.get_category_users('manual')
		followed_by = False

		if uscreen_name not in blocked_list:
			try:
				friendship = tw.t.friendships.show(source_screen_name=AUTH_SCREEN_NAME, target_screen_name=uscreen_name)

				if friendship["relationship"]["target"]["following"] == False and uscreen_name not in manual_list:
					print(STARTC + uscreen_name + " is not following." + ENDC)
					for category in categories:
						sheet.remove_user_from_category(category, uscreen_name)
				elif friendship["relationship"]["target"]["followed_by"] == False:
					print(STARTC + uscreen_name + " is a new Reply Guy!" + ENDC)
					tw.t.friendships.create(screen_name=uscreen_name, follow=False)
					tw.t.friendships.update(screen_name=uscreen_name, retweets=False)
					followed_by = True
				else:
					tw.t.friendships.update(screen_name=uscreen_name, retweets=False)
					followed_by = True
			except Exception as e:
				# mark as error in sheet
				for category in categories:
					cat_users = sheet.get_category_users(category)
					if uscreen_name in cat_users:
						sheet.overwrite_cell('error', category, ('D' if category.lower() == 'mentions' else 'B') + str(cat_users.index(uscreen_name) + ROW_OFFSET))
				display_error(e, 'AccountHandler.check_is_followed_by')

		return followed_by

	# -----------  Check if user is "newly whitelisted", determine unfollow  -----------
	def unfollow_after_newly_whitelisted_check(self, uscreen_name):
		tw = self.tw

		newly_whitelisted = self.add_tw_user_to_sheet_category(uscreen_name)
		if newly_whitelisted:
			print(STARTC + uscreen_name + ' is newly whitelisted.' + ENDC)
		else:
			unfollowed = tw.unfollow_twitter_user(uscreen_name)
			if unfollowed == True:
				print('Unfollowed ' + uscreen_name)
				return True

		return False

	# -----------  Remove users from categories if not following  -----------
	def remove_unfollowers_from_categories(self):
		sheet = self.sheet
		whitelist = sheet.get_category_users('whitelist')
		cleanup_cursor = sheet.get_cleanup_cursor()

		if cleanup_cursor in whitelist:
			cleanup_cursor = cleanup_cursor.lower()
			whitelist = whitelist[whitelist.index(cleanup_cursor):]
		elif cleanup_cursor != False:
			start_at_letter = [i for i in whitelist if i.startswith(cleanup_cursor[0][0])][0]
			whitelist = whitelist[whitelist.index(start_at_letter):]

		for screen_name in whitelist:
			uscreen_name = screen_name.strip().lower()
			self.check_is_followed_by(uscreen_name)

			sheet.overwrite_cleanup_cursor(uscreen_name)
			sleep_overlay(uscreen_name)

		return

	# -----------  Remove old mentions  -----------
	def remove_old_mentions(self):
		tw = self.tw
		sheet = self.sheet

		[removed_users, dm_screen_names] = sheet.remove_old_mentions()
		removed_users = list(set(removed_users))
		for screen_name in removed_users:
			uscreen_name = screen_name.lower()
			if not self.user_is_whitelisted(uscreen_name):
				print(STARTC + uscreen_name + ' has not tweeted at you in 6 months.' + ENDC)
				self.unfollow_after_newly_whitelisted_check(uscreen_name)
		for screen_name in dm_screen_names:
			uscreen_name = screen_name.lower()
			tw.send_direct_message(uscreen_name)

		sheet.remove_old_duplicate_category('mentions')
		return

	# -----------  Daily Tasks  -----------
	def dailies(self):
		self.reset_cursors()
		self.remove_old_mentions()
		self.unfollow_inactive_users()

		return

# ======================================
# =           Helper Options           =
# ======================================

def menu(tweeder):
	user_options = [
		"0. Daily tasks",
		"1. Unfollow users",
		"2. Update listed users",
		"3. Remove old mentions",
		"4. Clean category users",
		"5. Reset CURSORs",
		"6. Delete tweets older than 2 years",
		"7. Delete tweets without interactions",
		"8. Sleep (in case of rate limit)"
	]

	opts = Picker(
		title = 'What would you like to do?',
		options = user_options
	).getSelected()

	if opts == False:
		return opts

	for opt in opts:
		print("\n----------- " + opt + " -----------")
		if opt == user_options[0]:
			tweeder.dailies()
		elif opt == user_options[1]:
			tweeder.unfollow_inactive_users()
		elif opt == user_options[2]:
			tweeder.add_listed_users_to_whitelist(AUTH_SCREEN_NAME)
		elif opt == user_options[3]:
			tweeder.remove_old_mentions()
		elif opt == user_options[4]:
			tweeder.remove_unfollowers_from_categories()
		elif opt == user_options[5]:
			tweeder.reset_cursors()
		elif opt == user_options[6]:
			tweeder.tw.delete_archived_tweets()
		elif opt == user_options[7]:
			tweeder.tw.delete_tweets_without_interactions()
		elif opt == user_options[8]:
			answ = input('How many seconds should we sleep?: ')
			sleep_overlay('zzz', int(answ))
		else:
			return True

	answ = input("Would you like to do more? (Y/N) ")
	if answ.lower() in CANCEL_OPTIONS:
		return False

	return True

def main():
	running = True

	# ===== CONNECT TO RESOURCES AND CLASSES =====
	try:
		_tw = AccountHandler()
		_sheet = ExemptHandler(time.time())
		tweeder = Tweeder(_tw, _sheet)
		tweeder.sheet.overwrite_cell(str(datetime.now()), 'INFORMATION', 'B3')
		print("\nConnection complete!")
		sleep_overlay(STARTC + "Loading..." + ENDC, 3)
		print()
	except Exception as e:
		display_error(e, 'CONNECTION')
		sleep_overlay(STARTC + "Shutting down... Feel free to ctrl+c." + ENDC, 100)
		running = False
	# ===== CONNECTION COMPLETE =====

	while running:
		running = menu(tweeder)

	print("Thank you, come again!\n")
	return

if __name__ == '__main__':
	main()
