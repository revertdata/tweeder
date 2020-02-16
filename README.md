# Tweeder

> Scripts to clean my twitter account to cater to my own ticks.

🗣 Say hello! [@telepathics](https://twitter.com/telepathics) | [@revertdata](https://twitter.com/revertdata)

It's called Tweeder because my last name is Weed.

For the last 5 years, I kept a 1:1 following ratio on Twitter.  I recently decided to start only following people who I regularly interact with, instead.  This script also deletes certain tweets and keeps my account tidy.  Happy 2020 :)

## Installation

<!-- MarkdownTOC autolink="true" -->

- [1. Request your Twitter archive](#1-request-your-twitter-archive)
- [2. Set up IFTTT](#2-set-up-ifttt)
- [3. Customize your Google Sheets](#3-customize-your-google-sheets)
	- [Google Sheets Authentication](#google-sheets-authentication)
	- [Gspread Authentication](#gspread-authentication)
- [4. Create a Twitter Application](#4-create-a-twitter-application)

<!-- /MarkdownTOC -->

## 1. Request your Twitter archive

You can follow [this official tutorial](https://help.twitter.com/en/managing-your-account/how-to-download-your-twitter-archive) to download your Twitter archive.  This might take a while, depending on how many Tweets you have.  I had over 55,000 tweets over the span of 5 years, so it took about a half hour to generate.

Your archive is used to delete old tweets.  Twitter now only allows API calls for the last 3,500 tweets or something, so to dive into the deep-end, we need to gather the tweets manually.

After it's been downloaded, move the `tweet.json` file into this repo's main directory.

## 2. Set up IFTTT

I have an [IFTTT](https://ifttt.com/create) applet that runs whenever I receive a new Twitter mention, then stores a new row into a Google Sheet.

Use the following line to format each row:

```sql
=LOWER("{{UserName}}") ||| {{LinkToTweet}} ||| =DATEVALUE(SUBSTITUTE("{{CreatedAt}}"," at "," "))
```

**Some issues I've found so far include:**

* If you get an influx of tweets at once, it may skip some additions.  For example, [for this tweet](https://twitter.com/telepathics/status/1208839624422051846), a handful of people were not added, and were unfollowed as a result.
* It creates a new spreadsheet after ~2,000 rows. Temporary combats include 1.) deleting rows older than 6 months old, and 2.) deleting old mentions by the same user, keeping only their most recent reply.

## 3. Customize your Google Sheets

View my [active Google Sheets](https://docs.google.com/spreadsheets/d/1VVU6jz63JLqxooM4z01xxOvjrtjYvOmr9AvPBoOVDCA/edit#gid=0) data storage (my custom categories are hidden).

Upon the first IFTTT run, it will create a new spreadsheet (if there wasn't one already).

The following two sheets are **REQUIRED** to work with Tweeder:

1. `MENTIONS` - the sheet IFTTT will log your mentions.  It should remain the first sheet, since I don't think you can ask IFTTT to log to a separate sheet.
2. `WHITELIST` - a sorted, unique list of Twitter screen names who are whitelisted from unfollows.

Use the following line to create the basic WHITELIST:

```sql
=SORT(UNIQUE({MENTIONS!A2:A}))
```

You can also create other category sheets to use with Tweeder, and adjust your WHITELIST script.  Mine includes:

* FAVORITED (beta)
* RETWEETED (beta)
* VERIFIED
* NOTIFICATIONS
* LISTED
* MANUAL

So my WHITELIST function looks like this:

```sql
=SORT(UNIQUE({MENTIONS!A2:A;VERIFIED!A2:A;NOTIFICATIONS!A2:A;LISTED!A2:A;MANUAL!A2:A}))
```

**PLEASE NOTE** that I've made all of the ranges in this code to be `A2:A` because `A1` typically contains a heading.  There are no sheets that use `B:Z` because I want to be able to delete the entire row if that user is not following me.  `A2:A` contains a list of user screen_names.

### Google Sheets Authentication

Visit [this tutorial](https://developers.google.com/sheets/api/quickstart/python) and click on "Enable the Google Sheets API" to download the `credentials.json` file.

Then, install the Google Client Library using pip:

```console
pip install --upgrade google-api-python-client google-auth-httplib2 google-auth-oauthlib
```

You will also need to update the `g.py` file with your own SPREADSHEET_ID, which can be found in the URL of the Google Sheet you're editing.  For example, https://docs.google.com/spreadsheets/d/1VVU6jz63JLqxooM4z01xxOvjrtjYvOmr9AvPBoOVDCA/edit#gid=0 has the ID **1VVU6jz63JLqxooM4z01xxOvjrtjYvOmr9AvPBoOVDCA**.

```python
#!/usr/bin/env python3

SCOPES = 'https://www.googleapis.com/auth/spreadsheets'
GSPREAD_SCOPES = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
SPREADSHEET_ID = '1VVU6jz63JLqxooM4z01xxOvjrtjYvOmr9AvPBoOVDCA'
```

**NOTE**: after you first run the application, you will be asked to authenticate via logging in to your Google account.  This will create a necessary `token.json` file and give your console permission to access your Google Sheet.

### Gspread Authentication

Ok, bear with me here.  Not exactly sure what I was doing with the gspread authentication, since I was awake for about 37 hours when I was working with it.

Regardless, you can [follow this tutorial](https://gspread.readthedocs.io/en/latest/oauth2.html) to get a better understanding, and here is [how to enable the Google Drive API](https://developers.google.com/drive/api/v3/enable-drive-api).

You should be able to download a `service_credentials.json` file that looks like this:

```json
{
  "type": "service_account",
  "project_id": "xxx-123",
  "private_key_id": "123456",
  "private_key": "-----PRIVATE KEY-----",
  "client_email": "gspread@email.access",
  "client_id": "123456",
  "auth_uri": "https://accounts.google.com/o/oauth2/auth",
  "token_uri": "https://oauth2.googleapis.com/token",
  "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
  "client_x509_cert_url": "https://www.googleapis.com/"
}
```

## 4. Create a Twitter Application

After you [create a Twitter application](https://developer.twitter.com/en/apps), make a file called `t.py`in this project's main directory with the following credentials from your application's "Keys and tokens" settings:

```python
#!/usr/bin/env python3

CONSUMER_KEY='ABCDEFGHIJKLMNOPQRSTUVWXYZ'
CONSUMER_SECRET='ABCDEFGHIJKLMNOPQRSTUVWXYZ'
ACCESS_TOKEN_KEY='1234567890-ABCDEFGHIJKLMNOPQRSTUVWXYZ'
ACCESS_TOKEN_SECRET='ABCDEFGHIJKLMNOPQRSTUVWXYZ'
```

Make sure that your application has read/write access to your account.  I called mine "Tweeder by maryn", but you can call yours whatever you want.  You can use this cute little icon, if you don't want the default bird.

<p align="center">
  <img height="200" src="https://raw.githubusercontent.com/revertdata/tweeder/master/tweeder.PNG?token=ACZLNMUPMGJLG5UNCWANZS26CJINE">
</p>
