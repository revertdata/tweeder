#!/usr/bin/env python3

# =========================================
# for some reason, IFTTT likes to randomly
# shut off without notice, so this script
# is for whenever i need to manually
# insert tweets into the google sheet.
# =========================================

import subprocess

def cleanTweetForSheet():
  tweet = input("paste tweet here: ")

  print()
  data = '=LOWER("' + tweet[20:tweet.find('/status/')] + '")\n=LOWER("' + tweet + '")'
  subprocess.run("pbcopy", universal_newlines=True, input=data)
  print(data)
  print()


if __name__ == '__main__':
  while True:
    cleanTweetForSheet()
