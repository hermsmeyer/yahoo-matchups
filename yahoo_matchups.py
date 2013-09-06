#!/usr/bin/env python

# Goal: download list of matchps for the week from yahoo api, download the starting rosters for each team from yahoo api, 
# scrape projections from http://www.profootballfocus.com/toolkit/,
# match up players with projections, sum projections and print the scores for each matchup to screen.

from os import system
import re
import requests
from bs4 import BeautifulSoup
import sqlite3 as lite
from sys import exit
import argparse
import mechanize
import cookielib
import webbrowser
from rauth import OAuth1Service
from getpass import getpass

parser = argparse.ArgumentParser(
	description="yahoo_matchups v 0.1 - downloads and predicts the outcome of your yahoo fantasy football league's head to head games.",
	add_help=True)

parser.add_argument('-w', type=int, help='Enter the week of matchups to predict. (Ex: -w 1)')
parser.add_argument('-l', type=int, default=53449, help='Enter the league id. (Ex: -l 5344)')
parser.add_argument('-pid', type=int, default=2297, help='Enter the ProFootballFocus projections id for your custom league projections. (Ex: -pid 2297)')
args = parser.parse_args()

####################################################
##  The following variables must be user defined  ##
####################################################

# Get Yahoo API keys here:  http://developer.yahoo.com/fantasysports/
OAUTH_CONSUMER_KEY = ''
OAUTH_SHARED_SECRET = ''
DB = 'yahoo_matchups.sqlite'
# You can get the up to date game id for football at this url:
# http://developer.yahoo.com/yql/console/?q=select%20*%20from%20fantasysports.games%20where%20game_key%3D%27nfl%27%3B
GAME_ID = 314
LEAGUE_URL = 'http://fantasysports.yahooapis.com/fantasy/v2/league/' + str(GAME_ID) + '.l.' + str(args.l)	# 314 is the game id for nfl ffb 2013
																					

def connect_to_db() :
	
	con = None
	
	# We attempt to connect to our database
	try :
	    con = lite.connect(DB)
	    print " Yahoo Matchups v 0.1"
	    
	except lite.Error, e:
	    
	    print "Error %s:" % e.args[0]
	    exit(1)

	c = con.cursor()
	return c, con


def create_browser() :
	
	# We set up our mechanize browser
	br = mechanize.Browser()

	# We create our Cookie Jar
	cj = cookielib.LWPCookieJar()
	br.set_cookiejar(cj)

	# We set our mechanize browser options
	br.set_handle_equiv(True)
	br.set_handle_redirect(True)
	br.set_handle_referer(True)
	br.set_handle_robots(False)

	# We follow fast refreshes, but we don;t want to hang on longer refreshes
	br.set_handle_refresh(mechanize._http.HTTPRefreshProcessor(), max_time=1)

	# We fake our User-Agent
	br.addheaders = [('User-agent', 'Mozilla/5.0 (X11; U; Linux i686; en-US; rv:1.9.0.1) Gecko/2008071615 Fedora/3.0.1-1.fc9 Firefox/3.0.1')]
	return br, cj


def pff_login(br, cj) :
	
	user = raw_input(' Enter your ProFootballFocus username: ')
	passwd = getpass(' Enter your ProFootballFocus password: ')
	print " Logging into ProFootballFocus..."
	login_url = "https://www.profootballfocus.com/amember/member/index"
	if user and passwd :

		try :
			br.open(login_url)

			# We select the first (index zero) form
			br.select_form(nr=0)

			# We supply the user credentials
			br.form['amember_login'] = user
			br.form['amember_pass'] = passwd

			# We login
			br.submit()
			print " Logged in..."

		except :
			print " There was a problem logging into PFF. Did you enter the correct user name and password?"
	else :
		print " We can't project the games without projections, now can we? Consider getting a subscription to ProFootballFocus."
		exit(1)


def pff_scrape(br, cj, args) :
	
	url = 'http://www.profootballfocus.com/toolkit/data/' + str(args.pid) + '/'
	week = args.w
	print " Grabbing projections for week " + str(week)
	
	soup = BeautifulSoup(br.open(url + str(week) + '/all/'))
	clean_soup = soup.text.lstrip('{"aaData":').rstrip('}')
	player_list_a = clean_soup.replace('[', '').split('],')
	player_list = [x.replace(' ', ',') for x in player_list_a]

	if len(player_list) <= 1 :
		print " There was an issue scraping the projections. PFF may be updating their data. Try again in a moment."
	else :	
		print " Player list length is " + str(len(player_list))
	return player_list


def pff_store_projections(player_list, c, con) :
	
	c.execute("DROP TABLE IF EXISTS weekly_projections")
 	c.execute('CREATE TABLE weekly_projections(dummy INT, fname TEXT, lname TEXT, tm TEXT, op_team TEXT, dummy2 INT, pos TEXT, points REAL, dummy3 INT, dummy4 INT)')

 	for player in player_list :
 		player_split = player.split(",")

 		# Deal with the players with middle initials and suffixes. Incredibly hacky but better than mapping ids by hand...
 		if player_split[1] == '"Robert' :
 			if player_split[2] == 'Griffin' :
 				player_split = [x.replace('Griffin', 'Griffin III') for x in player_split]
 				player_split.pop(3)

 		if player_split[1] == '"Alex' :
 			if player_split[2] == 'D.' :
 				player_split = [x.replace('D.', 'Smith') for x in player_split]
 				player_split.pop(3)

 		if player_split[1] == '"Adrian' :
 			if player_split[2] == 'L.' :
 				player_split = [x.replace('L.', 'Peterson') for x in player_split]
 				player_split.pop(3)

 		if player_split[1] == '"Chris' :
 			if player_split[2] == 'D.' :
 				player_split = [x.replace('D.', 'Johnson') for x in player_split]
 				player_split.pop(3)

 		if player_split[1] == '"Steve' :
 			if player_split[2] == 'L.' :
 				player_split = [x.replace('L.', 'Smith') for x in player_split]
 				player_split.pop(3)

 		if player_split[1] == '"Mike' :
 			if player_split[2] == 'A.' :
 				player_split = [x.replace('A.', 'Williams') for x in player_split]
 				player_split.pop(3)

 		if player_split[1] == '"Zach' :
 			if player_split[2] == 'J.' :
 				player_split = [x.replace('J.', 'Miller') for x in player_split]
 				player_split.pop(3)

 		if len(player_split) == 10 :
			c.execute("INSERT INTO weekly_projections VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", player_split)
		
		# We use this this to find players with middle initials and suffixes that need special treatment
		else :
			print " Found players that need custom code. Printing..."
			print player_split

 	c.execute("UPDATE weekly_projections SET fname = REPLACE(fname, '\"', '')")
 	c.execute("UPDATE weekly_projections SET lname = REPLACE(lname, '\"', '')")
	c.execute("UPDATE weekly_projections SET tm = REPLACE(tm, '\"', '')")
	c.execute("UPDATE weekly_projections SET pos = REPLACE(pos, '\"', '')")
	c.execute("UPDATE weekly_projections SET points = REPLACE(points, '\"', '')")
	con.commit()

	print " Data successfully stored."


def yahoo_oauth() :
	
	# We define a bunch of starter variables for rauth.
	ACCESS_TOKEN_URL = 'https://api.login.yahoo.com/oauth/v2/get_token'
	AUTHORIZE_URL = 'https://api.login.yahoo.com/oauth/v2/request_auth'
	REQUEST_TOKEN = 'https://api.login.yahoo.com/oauth/v2/get_request_token'

	if OAUTH_CONSUMER_KEY and OAUTH_SHARED_SECRET :
		# We use the rauth library to set up an Oauth session
		yahoo = OAuth1Service( 
				name='yahoo',
				consumer_key=OAUTH_CONSUMER_KEY,
				consumer_secret=OAUTH_SHARED_SECRET,
				request_token_url=REQUEST_TOKEN,
				access_token_url=ACCESS_TOKEN_URL,
				authorize_url=AUTHORIZE_URL,
				base_url='https://api.login.yahoo.com/oauth/v2/')
		return yahoo

	else :
		print " Yahoo API login failed. You need to enter your api keys into the script."
		print " Get your keys here: http://developer.yahoo.com/fantasysports/"
		exit(1)

def yahoo_get_credentials(c, con) :
	
	print " Checking for previous Yahoo credentials..."

	c.execute('SELECT request_token FROM user')
	r_token = c.fetchone()
	request_token = r_token[0]

	c.execute('SELECT request_token_secret FROM user')
	r_token_secret = c.fetchone()
	request_token_secret = r_token_secret[0]
	
	c.execute('SELECT pin FROM user')
	db_pin = c.fetchone()
	pin = db_pin[0]
	return request_token, request_token_secret, pin


def yahoo_generate_new_credentials(yahoo, c ,con) :
	
	'''Uses rauth to request OAuth1Service credentials from the Yahoo sports api.'''
	
	# We use rauth to request access tokens and store them in the yahoo_players.sqlite database
	request_token, request_token_secret = yahoo.get_request_token(data = { 'oauth_callback': "oob" }) 

	# Print some feedback and let the user know a new window is opening and that they need to enter a pin.
	print " Request Token:" 
	print " - oauth_token = %s" % request_token 
	print " - oauth_token_secret = %s" % request_token_secret 
	auth_url = yahoo.get_authorize_url(request_token) 
	print ' Opening browser window... '
	webbrowser.open_new_tab(auth_url)
	pin = raw_input(' Enter the oauth_verifier code from the browser url: ')
	
	c.execute("DROP TABLE IF EXISTS user")
	c.execute('CREATE TABLE user(request_token TEXT, request_token_secret TEXT,pin TEXT)')
	c.execute('INSERT INTO user(request_token,request_token_secret,pin) VALUES(?, ?, ?)', (request_token, request_token_secret, pin))
	con.commit()


def yahoo_login(credentials, yahoo) :
	
	session = yahoo.get_auth_session(credentials[0], credentials[1], method='POST', data={'oauth_verifier': credentials[2]})
	print " Authenticated!"
	return session


def yahoo_get_teams(session) :
	
	teams = []
	print " Getting teams..."	
	r = session.get(LEAGUE_URL + '/teams')
	soup = BeautifulSoup(r.text)
	for item in soup.find_all("team") :	# search for all tags inside of team. returns a soup object so we can further refine in the loop
		teams.append(item.team_key.text + ',' + item.find('name').string)	# item.find('name').string allows us to grab the xml field 'name'
	return teams															# BeautifulSoup has 'name' in its namespace, so this is the workaround
	
def yahoo_store_teams(teams, c ,con) :
	
	c.execute("DROP TABLE IF EXISTS teams")
	c.execute('CREATE TABLE teams(id TEXT, tm TEXT)')

	for team in teams :
		team_insert = team.split(',') 		
		c.execute('INSERT INTO teams VALUES(?, ?)', (team_insert))
		con.commit()
	print " Data successfully stored."


def yahoo_get_rosters(session, team_id) :
	
	rosters = []
	count = 0
	print " Downloading rosters..."	
	for team in team_id :
		r = session.get('http://fantasysports.yahooapis.com/fantasy/v2/team/' + str(team[0]) + '/roster')	# http://fantasysports.yahooapis.com/fantasy/v2/team/223.l.431.t.9/roster;week=2
		soup = BeautifulSoup(r.text)
		for player in soup.find_all('player') :
			if player.selected_position.position.text != 'BN' :
				if player.selected_position.position.text != 'DEF' :
					rosters.append(str(team[0]) + ',' + player.find('name').first.string + ',' + player.find('name').last.string + ',' + player.editorial_team_abbr.string)
				elif player.selected_position.position.text == 'DEF' :
					rosters.append(str(team[0]) + ',' + player.find('name').first.string + ',' + "" + ',' +"")
		system('clear')	# Hack to make the counter look like it is progressing
		count += 1
		print " Getting starting roster " + str(count) + "/" + str(len(team_id))
	return rosters


def yahoo_store_rosters(rosters,c ,con) :
	
	c.execute("DROP TABLE IF EXISTS rosters")
	c.execute('CREATE TABLE rosters(id TEXT, fname TEXT, lname TEXT, tm TEXT)')

	for roster in rosters :
		roster_insert = roster.split(',') 		
		c.execute('INSERT INTO rosters VALUES(?, ?, ?, ?)', (roster_insert))
		con.commit()
	print " Data successfully stored."


def yahoo_get_matchups(team_id, args, session) :
	
	h2h = []
	print " Getting H2H matchups..."	

	r = session.get(LEAGUE_URL + '/scoreboard/matchups')
	soup = BeautifulSoup(r.text)
	all_matchups = soup.league.scoreboard.matchups
	matchup = [b.string for b in all_matchups.findAll('team_key')]

	for i in range(0, len(matchup), 2) :
		h2h.append(str(matchup[i]) + "," + str(matchup[i + 1]))	

	return h2h			
	

def yahoo_store_matchups(h2h, c ,con) :
	
	c.execute("DROP TABLE IF EXISTS h2h")
	c.execute('CREATE TABLE h2h(home TEXT, away TEXT)')

	for game in h2h :
		game_insert = game.split(',') 		
		c.execute('INSERT INTO h2h VALUES(?, ?)', (game_insert))
		con.commit()
	print " Data successfully stored."


def yahoo_get_tm_id(c, con) :
	
	team_id = []
	c.execute('SELECT id FROM teams')
	team_id = c.fetchall()
	return team_id


def yahoo_clean_db(c, con) :
	
	# We make sure that all our fields match in both db tables so we can get a good join
	c.execute("UPDATE rosters SET tm = UPPER(tm)")
	c.execute("UPDATE rosters SET tm = 'HST' WHERE tm = 'HOU'")
	c.execute("UPDATE rosters SET tm = 'CLV' WHERE tm = 'CLE'")
	c.execute("UPDATE rosters SET tm = 'BLT' WHERE tm = 'BAL'")
	c.execute("UPDATE rosters SET tm = 'JAX' WHERE tm = 'JAC'")
	c.execute("UPDATE rosters SET tm = 'SL' WHERE tm = 'STL'")
	c.execute("UPDATE rosters SET tm = 'ARZ' WHERE tm = 'ARI'")
	con.commit()


def yahoo_display_matchups(args, c, con) :
	
	c.execute("DROP TABLE IF EXISTS weekly_totals")
	c.execute('CREATE TABLE weekly_totals(id TEXT, tm_name TEXT, total REAL)')
	c.execute('SELECT id FROM teams')
	teams = c.fetchall()
	
	for team in teams :
		points = 0
		c.execute('SELECT lname, fname, tm, points FROM weekly_projections NATURAL JOIN rosters WHERE rosters.id = ?', team)
		players = c.fetchall()

		for player in players :
			points = points + player[3]
		c.execute('SELECT tm FROM teams WHERE teams.id = ?', team)
		tm_name = c.fetchone()
		c.execute('INSERT INTO weekly_totals VALUES(?, ?, ?)', (team[0], tm_name[0], points))

	# for matchup in h2h :
	# 	c.execute('SELECT lname, fname, tm, points FROM weekly_totals NATURAL JOIN rosters WHERE rosters.id = ?', (matchup[0],))

	con.commit()

	c.execute('SELECT * FROM h2h')
	h2h = c.fetchall()
	
	system('clear')
	print " #### Projected Week " + str(args.w) + " Results ####"
	print '\n'
	for matchup in h2h :
		c.execute('SELECT tm_name, total FROM weekly_totals WHERE weekly_totals.id = ?', (matchup[0],))
		home = c.fetchone()
		c.execute('SELECT tm_name, total FROM weekly_totals WHERE weekly_totals.id = ?', (matchup[1],))
		away = c.fetchone()

		if len(home[0]) >= 17 :
			print " " + str(home[0]) + "\t" + str(round(home[1],1))
		elif len(home[0]) <= 8 :
			print " " + str(home[0]) + "\t\t\t" + str(round(home[1],1))
		else :
			print " " + str(home[0]) + "\t\t" + str(round(home[1],1))

		if len(away[0]) >= 17 :
			print " " + str(away[0]) + "\t" + str(round(away[1],1))
		elif len(away[0]) <= 8 :
			print " " + str(away[0]) + "\t\t\t" + str(round(away[1],1))
		else :
			print " " + str(away[0]) + "\t\t" + str(round(away[1],1))
		print "\n"


def main() :
	
	c, con = connect_to_db()
	# We login and scrape projections from PFF
	br, cj = create_browser()
	pff_login(br, cj)
	player_list = pff_scrape(br, cj, args)
	pff_store_projections(player_list, c, con)
	
	# We login to Yahoo Sports API using Oauth
	yahoo = yahoo_oauth()
	# We check if we have good yahoo credentials, if not we generate some fresh new ones. No idea why yahoo expires tokens so quickly.
	try : 
		credentials = yahoo_get_credentials(c, con)
		session = yahoo_login(credentials, yahoo)

	except :
		print " Unable to authenticate. Requesting a new pin..."
		c.execute("DROP TABLE IF EXISTS user")
		c.execute('CREATE TABLE user(request_token TEXT, request_token_secret TEXT,pin TEXT)')
		con.commit()

		yahoo_generate_new_credentials(yahoo,c ,con)
		credentials = yahoo_get_credentials(c, con)
		session = yahoo_login(credentials, yahoo)
	
	teams = yahoo_get_teams(session)
	yahoo_store_teams(teams, c, con)
	team_id = yahoo_get_tm_id(c, con)
	rosters = yahoo_get_rosters(session, team_id)
	yahoo_store_rosters(rosters, c, con)
	yahoo_clean_db(c, con)
	h2h = yahoo_get_matchups(team_id, args, session)
	yahoo_store_matchups(h2h, c, con)
	yahoo_display_matchups(args, c, con)
	con.close()


if __name__ == '__main__':
    main()