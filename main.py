#!/usr/bin/env python
#
# Copyright 2007 Google Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# 
# Written by Ryan Orr at hackWaterloo

import webapp2
import sys
import os
import jinja2
import json
from google.appengine.ext import ndb

sys.path.insert(0, 'tweepy.zip')
import tweepy

template_dir = os.path.join(os.path.dirname(__file__), 'templates')
jinja_env = jinja2.Environment(loader = jinja2.FileSystemLoader(template_dir), autoescape = True)

#Removed for github
consumer_key=""
consumer_secret=""
access_token=""
access_token_secret=""
        
# Build a new oauth handler and connect to twitter api
auth = tweepy.OAuthHandler(consumer_key, consumer_secret)
auth.set_access_token(access_token, access_token_secret)
api = tweepy.API(auth, secure=True)

def get_rls():
	rls = api.rate_limit_status()
	app_rls = rls['resources']['application']['/application/rate_limit_status']['remaining']
	search_rls = rls['resources']['search']['/search/tweets']['remaining']
	if app_rls > 0:
		return search_rls
	return 0
	
print get_rls()

faces = {'angry' : 56865,
         'tears' : 56877,
         'crying' : 56889,
         'smile' : 56842,
         'frown' : 56864}

happy_text = [":)", ":-)", ";)", ";-)", ":D", "XD", ":-D"]
sad_text = [":(", ":-(", ":'("]
angry_text = [">:(", ">:-("]

emotions = ["angry", "happy", "sad"]

class Tweet(ndb.Model):
	emotion = ndb.StringProperty(required = True)
	tweet = ndb.StringProperty(required = True)
	
class TweetCount(ndb.Model):
	emotion = ndb.StringProperty(required = True)
	count = ndb.IntegerProperty(required = True)
	
class TweetCurrentId(ndb.Model):
	emotion = ndb.StringProperty(required = True)
	curr_id = ndb.IntegerProperty(required = True)
	
class Synonym(ndb.Model):
	emotion = ndb.StringProperty(required = True)
	synonym = ndb.StringProperty(required = True)
	curr_id = ndb.IntegerProperty(required = True)	

def get_next_emotion():
	query = TweetCount.query()
	lowest = 999999999999999
	emotion = ""
	emotes = ["angry", "happy", "sad"]
	for q in query:
		emotes.remove(q.emotion)
		if q.count < lowest:
			lowest = q.count
			emotion = q.emotion
	if emotes != []:
		return emotes[0]
	return emotion
	
def update():
	#setup data structure
	data = {}
	for emotion in emotions:
		data[emotion] = {}
		data[emotion]["synonyms"] = {}
		data[emotion]["tweet_count"] = 0
		query = TweetCurrentId.query(TweetCurrentId.emotion==emotion)
		curr_id = 0
		for cid in query.fetch():
			curr_id = cid.curr_id
		data[emotion]["id"] = curr_id
		data[emotion]["cursor"] = tweepy.Cursor(api.search, q="#"+emotion, lang="en", since_id=curr_id)
		
	#need to populate synonyms	
	data["angry"]["synonyms"]["annoyed"] = {"id": 0}
	data["angry"]["synonyms"]["pissed"] = {"id": 0}
	data["angry"]["synonyms"]["makesmemad"] = {"id": 0}
	data["sad"]["synonyms"]["tears"] = {"id": 0}
	data["sad"]["synonyms"]["crying"] = {"id": 0}
	data["sad"]["synonyms"]["makesmesad"] = {"id": 0}
	data["sad"]["synonyms"]["sadface"] = {"id": 0}
	data["sad"]["synonyms"][":("] = {"id":0}
	data["happy"]["synonyms"]["glad"] = {"id": 0}
	data["happy"]["synonyms"]["makesmehappy"] = {"id": 0}
	data["happy"]["synonyms"]["lol"] = {"id": 0}
	data["happy"]["synonyms"][":)"] = {"id":0}
	data["happy"]["synonyms"]["fun"] = {"id":0}

	for emotion in emotions:
		query = Synonym.query(Synonym.emotion==emotion)
		done = []
		for syn in query.fetch():
			done.append(syn.synonym)
			data[emotion]["synonyms"][syn.synonym] = {}
			data[emotion]["synonyms"][syn.synonym]["id"] = syn.curr_id
			data[emotion]["synonyms"][syn.synonym]["cursor"] = tweepy.Cursor(api.search, q="#"+syn.synonym, lang="en", since_id=syn.curr_id)
		for syn in data[emotion]["synonyms"]:
			if syn not in done:
				data[emotion]["synonyms"][syn] = {}
				data[emotion]["synonyms"][syn]["id"] = 0
				data[emotion]["synonyms"][syn]["cursor"] = tweepy.Cursor(api.search, q="#"+syn, lang="en", since_id=0)

	#pull any new tweets
	cont = True
	while get_rls() > 15 and cont:
		emotion = get_next_emotion()
		tweets = data[emotion]["cursor"].items(15)
		cont = False
		for tweet in tweets:
			cont = True
			tw = Tweet(emotion=emotion, tweet=tweet.text)
			tw.put()
			if tweet.id > data[emotion]["id"]:
				data[emotion]["id"] = tweet.id
			data[emotion]["tweet_count"] = data[emotion]["tweet_count"] + 1
		for syn in data[emotion]["synonyms"]:
			tweets = data[emotion]["synonyms"][syn]["cursor"].items(15)
			for tweet in tweets:
				cont = True
				tw = Tweet(emotion=emotion, tweet=tweet.text)
				tw.put()
				if tweet.id > data[emotion]["synonyms"][syn]["id"]:
					data[emotion]["synonyms"][syn]["id"] = tweet.id
				data[emotion]["tweet_count"] = data[emotion]["tweet_count"] + 1
	
	#update count and id values in db
	for emotion in emotions:
		query = TweetCurrentId.query(TweetCurrentId.emotion==emotion)
		flag = False
		for cid in query.fetch():
			flag = True
			cid.curr_id = data[emotion]["id"]
			cid.put()
		if not flag:
			tci = TweetCurrentId(emotion=emotion, curr_id=data[emotion]["id"])
			tci.put()
		flag = False
		query = TweetCount.query(TweetCount.emotion==emotion)
		for tc in query.fetch():
			flag = True
			tc.count = tc.count + data[emotion]["tweet_count"]
			tc.put()	
		if not flag:
			tc = TweetCount(emotion=emotion, count=data[emotion]["tweet_count"])
			tc.put()
		query = Synonym.query(Synonym.emotion==emotion)
		done = []
		for syn in query.fetch():
			flag = True
			syn.curr_id = data[emotion]["synonyms"][syn.synonym]["id"]
			syn.put()
			done.append(syn.synonym)
		for syn in data[emotion]["synonyms"]:
			if syn not in done:
				s = Synonym(emotion=emotion, synonym=syn, curr_id=data[emotion]["synonyms"][syn]["id"])
				s.put()

def lookup_topic(topic):
	data = {}
	for emotion in emotions:
		data[emotion] = {}
		data[emotion]["tweet_count"] = 0
		data[emotion]["tweets"] = []
		data[emotion]["id"] = 0
		data[emotion]["word_count"] = 0
		data[emotion]["synonyms"] = {}

	data["angry"]["synonyms"]["annoyed"] = {"id": 0}
	data["angry"]["synonyms"]["pissed"] = {"id": 0}
	data["angry"]["synonyms"]["makesmemad"] = {"id": 0}
	data["sad"]["synonyms"]["tears"] = {"id": 0}
	data["sad"]["synonyms"]["crying"] = {"id": 0}
	data["sad"]["synonyms"]["makesmesad"] = {"id": 0}
	data["sad"]["synonyms"]["sadface"] = {"id": 0}
	data["sad"]["synonyms"][":("] = {"id":0}
	data["happy"]["synonyms"]["glad"] = {"id": 0}
	data["happy"]["synonyms"]["makesmehappy"] = {"id": 0}
	data["happy"]["synonyms"]["lol"] = {"id": 0}
	data["happy"]["synonyms"][":)"] = {"id":0}
	data["happy"]["synonyms"]["fun"] = {"id":0}

	for emotion in emotions:
		query = Tweet.query(Tweet.emotion==emotion)
		for tweet in query.fetch():
			data[emotion]["tweets"].append(tweet.tweet)
		query = TweetCurrentId.query(TweetCurrentId.emotion==emotion)
		for id in query.fetch():
			data[emotion]["id"] = id.curr_id
		query = TweetCount.query(TweetCount.emotion==emotion)
		for count in query.fetch():
			data[emotion]["tweet_count"] = count.count
	
		query = Synonym.query(Synonym.emotion==emotion)
		for syn in query.fetch():
			data[emotion]["synonyms"][syn.synonym]["id"] = syn.curr_id

	words = {}
	for emotion in emotions:
		for tweet in data[emotion]["tweets"]:
			for word in tweet.split():
				word = word.replace("#", "").replace(".", "").replace("'", "").replace(",", "").replace('"', "").replace("(", "").replace(")", "")
				if "http" in word or "@" in word:
					continue
				if word not in words:
					words[word] = {}
					for emote in emotions:
						words[word][emote] = 0
				words[word][emotion] = words[word][emotion] + 1
				data[emotion]["word_count"] = data[emotion]["word_count"] + 1

	tweet_results = []
	cursor = tweepy.Cursor(api.search, q=topic, lang="en", since_id = 0)
	if get_rls() > 5:
		for tweet in cursor.items(30):
			tweet_results.append(tweet.text)
	else:
		print "Sorry, please wait for rate-limiting to increase"

	final_tally = {"angry":[], "happy":[], "sad":[], "Unknown":[]}
	
	for tweet in tweet_results:
		emotion = "Unknown"
		for text in sad_text:
			if text in tweet:
				emotion = "sad"
		for char in tweet:
			if ord(char) == faces['crying']:
				emotion = "sad"
			if ord(char) == faces['tears']:
				emotion = "sad"
		for text in angry_text:
			if text in tweet:
				emotion = "angry"
		for char in tweet:
			if ord(char) == faces['angry']:
				emotion = "angry"
			if ord(char) == faces['frown']:
				emotion = "angry"
		for text in happy_text:
			if text in tweet:
				emotion = "happy"
		for char in tweet:
			if ord(char) == faces['smile']:
				emotion = "happy"

		if emotion in emotions:
			final_tally[emotion].append(tweet)
			continue
		
		count = {"angry":0, "happy":0, "sad":0}
		for word in tweet.split():
			word_score = 0.0
			best_emotion = "Unknown"
			if word in words:
				for emotion in emotions:
					score = float(words[word][emotion])/float(data[emotion]["word_count"])
					if score > word_score:
						word_score = score
						best_emotion = emotion
				count[best_emotion] = count[best_emotion] + 1
		best_emotion = "Unknown"
		best_score = 0
		for emotion in emotions:
			if count[emotion] > best_score:
				best_emotion = emotion
				best_score = count[emotion]
		final_tally[best_emotion].append(tweet)
		
		
		#update datastore counts
		query = TweetCount.query(TweetCount.emotion==emotion)
		for tc in query.fetch():
			tc.count = data[emotion]["tweet_count"]
			tc.put()
			
	return final_tally

class Handler(webapp2.RequestHandler):
    def write(self, *a, **kw):
        self.response.out.write(*a, **kw)
    
    def render_str(self, template, **params):
        t = jinja_env.get_template(template)
        return t.render(params)

    def render(self, template, **kw):
        self.write(self.render_str(template, **kw))
        
	
class MainPage(Handler):
    def get(self):
    	self.render("main.html")
        
    def post(self):
    	query = str(self.request.get("query"))
    	self.redirect("/search?q=%s" % query)
    	
class ChangePage(Handler):
	def post(self):
		result = json.loads(self.request.body)
		for tweet in result["atweets"]:
			tw = Tweet(emotion="angry", tweet=tweet)
			tw.put()
		query = TweetCount.query(TweetCount.emotion=="angry")
		for tc in query.fetch():
			tc.count = tc.count + len(result["atweets"])
			tc.put()
		for tweet in result["htweets"]:
			tw = Tweet(emotion="happy", tweet=tweet)
			tw.put()
		query = TweetCount.query(TweetCount.emotion=="happy")
		for tc in query.fetch():
			tc.count = tc.count + len(result["htweets"])
			tc.put()
		for tweet in result["stweets"]:
			tw = Tweet(emotion="sad", tweet=tweet)
			tw.put()
		query = TweetCount.query(TweetCount.emotion=="sad")
		for tc in query.fetch():
			tc.count = tc.count + len(result["stweets"])
			tc.put()
    	
class SearchPage(Handler):
	def get(self):
		query = str(self.request.get("q"))
		result = lookup_topic(query)
		self.render("result.html", topic=query, happy=result["happy"], angry=result["angry"], sad=result["sad"], unknown=result["Unknown"], hcount=len(result["happy"]), acount=len(result["angry"]), scount=len(result["sad"]), ucount=len(result["Unknown"]))
											
class UpdatePage(Handler):
	def get(self):
		self.render("update.html")
	
	def post(self):
		self.redirect('/updated')
		
class UpdatedPage(Handler):
	def get(self):
		update()		
		query = TweetCount.query()
		for q in query.fetch():
			print q.emotion, q.count
		self.render("finished.html")
		
app = webapp2.WSGIApplication([
        ('/', MainPage),
        ('/search', SearchPage),
        ('/change', ChangePage),
        ('/update', UpdatePage),
        ('/updated', UpdatedPage)
    ], debug=True)