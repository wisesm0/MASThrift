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
import webapp2
import urllib2
import json
import logging
import cgi
import hashlib
from google.appengine.api import mail
from google.appengine.ext import ndb
from google.appengine.api import images

from constants import CATEGORIES, PER_PAGE, CATEGORY_SMALL_TO_BIG_MAP

START_URL = "https://graph.facebook.com/v2.2/199456403537988/feed?access_token=CAANI8ZBCAeOwBAHy59OJRb3B9y9X9aNn2XekTCjBsEWlR4H71M0srnqT4DJ6fnZBvPfilH8Nm4xXBYAZA3JwMqD5ElrlcptoNaEDZCRYtRTaPqhRqio7S6ioxTYXOT2ABANENj2mrHF6FNBv6et3X7hrbMzsIU8ZBK3YN5LlcNzAoQFpBB3HtNw354QdVggfLAemF4fzElS3nVRB6yOqE"
#To get comments from facebook:
#199456403537988_453511081465851/comments
#https://graph.facebook.com/v2.2/199456403537988_453511081465851/comments?access_token=CAANI8ZBCAeOwBAHy59OJRb3B9y9X9aNn2XekTCjBsEWlR4H71M0srnqT4DJ6fnZBvPfilH8Nm4xXBYAZA3JwMqD5ElrlcptoNaEDZCRYtRTaPqhRqio7S6ioxTYXOT2ABANENj2mrHF6FNBv6et3X7hrbMzsIU8ZBK3YN5LlcNzAoQFpBB3HtNw354QdVggfLAemF4fzElS3nVRB6yOqE
DEFAULT_GUESTBOOK_NAME = 'default_guest'


def categorize(description):
    if description:
        words = description.split()
        for category_name, keyword_dict in CATEGORIES:
            for word in words:
                if word.lower() in keyword_dict:
                    return category_name
    return "Others"

def guestbook_key(guestbook_name=DEFAULT_GUESTBOOK_NAME):
    """Constructs a Datastore key for a Guestbook entity.
    """
    return ndb.Key('Guestbook', guestbook_name)

class Listing(ndb.Model):
    """Models one listing/posting on facebook """
    title = ndb.StringProperty(indexed=True)
    message = ndb.StringProperty(indexed=True)
    category = ndb.StringProperty(indexed=True)
    date = ndb.StringProperty(indexed=True)
    picture = ndb.StringProperty(indexed=False)
    post_id = ndb.StringProperty(indexed=True)
    author_name = ndb.StringProperty(indexed=False)
    author_id = ndb.StringProperty(indexed=True)
    link_to_post = ndb.StringProperty(indexed=False)
    image_post = ndb.BlobProperty()
    tags = ndb.StringProperty(repeated=True)

class Authenticate(ndb.Model):
    username = ndb.StringProperty(indexed=True)
    password = ndb.StringProperty(indexed=True)


class DeleteAllHandler(webapp2.RequestHandler):
    def get(self):
        ndb.delete_multi(Listing.query().fetch(keys_only=True))
        self.response.headers['Access-Control-Allow-Origin'] = '*'
        self.response.write("Deleted all keys")
        
class updatedbHandler(webapp2.RequestHandler):
    """
    This function take all the history from Facebook group and update it in our database
    We need not run this 
    """
    def get(self):
        url = START_URL
        cnt = 0
        # debug_string = ""
        for page_no in range(30):
            json_response = urllib2.urlopen(url)
            data = json.load(json_response)
            # debug_string += "Page no fetching is " + str(page_no) + "\n"
            for item in data['data']:
                res = Listing.query(Listing.post_id == item['id'])
                if res.count() == 0:
                    d = {}
                    if 'message' in item:
                        messagez = item['message']
                    else:
                        messagez = ""
                    if messagez=="":
                        continue
                    title = " ".join(messagez.split()[:5]) + " ..."
                    d['message'] = messagez
                    d['title'] = title

                    if 'picture' in item:
                        d['picture'] = item['picture']
                    else:
                        d['picture'] = ""
                    new_listing = Listing(parent=guestbook_key(DEFAULT_GUESTBOOK_NAME))
                    new_listing.title = d['title']
                    new_listing.message = d['message'][0:500]
                    new_listing.tags = d['message'][0:500].split()
                    new_listing.post_id = item['id']
                    new_listing.date = item['created_time']
                    new_listing.author_id = item['from']['id']
                    new_listing.author_name = item['from']['name']
                    # debug_string += "Messages : " + d['message'] + "\n"
                    # debug_string += "Category : " + categorize(d['message']) + "\n"
                    new_listing.category = categorize(d['message'])
                    new_listing.picture = d['picture']
                    if 'link' in item:
                        new_listing.link_to_post = item['link']
                    else:
                        new_listing.link_to_post = item['actions'][0]['link']
                    new_listing.put()
                    cnt += 1
            url = data['paging']['next']
        self.response.headers['Access-Control-Allow-Origin'] = '*'
        self.response.write("Updated the database with " + str(cnt) + " new entries")


class CategoryHandler(webapp2.RequestHandler):
    def get(self, cat, page_no):
        category = str(cat)
        page_no = int(page_no)
        category_big = CATEGORY_SMALL_TO_BIG_MAP[category]
        logging.debug("Category received is " + category_big)
        result = Listing.query(Listing.category == category_big).order(-Listing.date);
        listings_list = []
        cnt = 0
        cont_count = 0
        # debug_string = []
        for listing in result:
            cnt = cnt + 1
            if cnt > (PER_PAGE * (page_no - 1)) and cnt <= (PER_PAGE * page_no):
                d = {}
                d['message'] = listing.message
                d['title'] = listing.title
                d['post_id'] = listing.post_id
                d['author_id'] = listing.author_id
                d['author_name'] = listing.author_name
                d['category'] = listing.category
                if listing.picture == "":
                    if listing.image_post is not None and listing.image_post != "":
                        d['picture'] = str("http://2.genuine-amulet-864.appspot.com/img?img_id=") + listing.key.urlsafe()
                d['picture'] = listing.picture
                d['date'] = str(listing.date)
                d['link_to_post'] = listing.link_to_post
                listings_list.append(d)
        self.response.headers['Access-Control-Allow-Origin'] = '*'
        js = json.dumps(listings_list)
        self.response.write(js)


class UserHandler(webapp2.RequestHandler):
    def get(self, author_id, page_no):
        author_id = str(author_id)
        page_no = int(page_no)
        result = Listing.query(Listing.author_id == author_id).order(-Listing.date);
        listings_list = []
        cnt = 0
        cont_count = 0
        # debug_string = []
        for listing in result:
            cnt = cnt + 1
            if cnt > (PER_PAGE * (page_no - 1)) and cnt <= (PER_PAGE * page_no):
                d = {}
                d['message'] = listing.message
                d['title'] = listing.title
                d['post_id'] = listing.post_id
                d['author_id'] = listing.author_id
                d['author_name'] = listing.author_name
                d['category'] = listing.category
                if listing.picture == "":
                    if listing.image_post is not None and listing.image_post != "":
                        d['picture'] = str("http://2.genuine-amulet-864.appspot.com/img?img_id=") + listing.key.urlsafe()
                else:
                    d['picture'] = listing.picture
                d['date'] = str(listing.date)
                d['link_to_post'] = listing.link_to_post
                listings_list.append(d)
        self.response.headers['Access-Control-Allow-Origin'] = '*'
        js = json.dumps(listings_list)
        self.response.write(js)


class SearchHandler(webapp2.RequestHandler):
    def get(self, search_str, page_no):
        search_str = str(search_str)
        page_no = int(page_no)
        result = Listing.query(Listing.tags.IN([search_str]) ).order(-Listing.date);
        listings_list = []
        cnt = 0
        cont_count = 0
        # debug_string = []
        for listing in result:
            cnt = cnt + 1
            if cnt > (PER_PAGE * (page_no - 1)) and cnt <= (PER_PAGE * page_no):
                d = {}
                d['message'] = listing.message
                d['title'] = listing.title
                d['post_id'] = listing.post_id
                d['author_id'] = listing.author_id
                d['author_name'] = listing.author_name
                d['category'] = listing.category
                if listing.picture == "":
                    if listing.image_post is not None and listing.image_post != "":
                        d['picture'] = str("http://2.genuine-amulet-864.appspot.com/img?img_id=") + listing.key.urlsafe()
                d['picture'] = listing.picture
                d['date'] = str(listing.date)
                d['link_to_post'] = listing.link_to_post
                listings_list.append(d)
        js = json.dumps(listings_list)
        self.response.headers['Access-Control-Allow-Origin'] = '*'
        self.response.write(js)




class PageHandler(webapp2.RequestHandler):
    def get(self, page_no):
        page_no = int(page_no)
        logging.debug("Page no received is " + str(page_no))
        result = Listing.query().order(-Listing.date);
        listings_list = []
        cnt = 0
        cont_count = 0
        # debug_string = []
        for listing in result:
            cnt = cnt + 1
            if cnt > (PER_PAGE * (page_no - 1)) and cnt <= (PER_PAGE * page_no):
                d = {}
                d['message'] = listing.message
                d['title'] = listing.title
                d['post_id'] = listing.post_id
                d['author_id'] = listing.author_id
                d['author_name'] = listing.author_name
                d['category'] = listing.category
                if listing.picture == "":
                    if listing.image_post:
                        d['picture'] = str("http://2.genuine-amulet-864.appspot.com/img?img_id=") + listing.key.urlsafe()
                else:
                    d['picture'] = listing.picture
                d['date'] = str(listing.date)
                d['link_to_post'] = listing.link_to_post
                listings_list.append(d)
        js = json.dumps(listings_list)
        self.response.headers['Access-Control-Allow-Origin'] = '*'
        self.response.write(js)

# [START image_handler]
class Image(webapp2.RequestHandler):
    def get(self):
        listing_key = ndb.Key(urlsafe=self.request.get('img_id'))
        listing = listing_key.get()
        self.response.headers['Access-Control-Allow-Origin'] = '*'
        if listing.image_post:
            self.response.headers['Content-Type'] = 'image/png'
            self.response.out.write(listing.image_post)
        else:
            self.response.out.write('')

class PostListingHandler(webapp2.RequestHandler):
    def post(self):
        content = cgi.escape(self.request.get('content'))
        new_listing = Listing(parent=guestbook_key(DEFAULT_GUESTBOOK_NAME))
        new_listing.title = cgi.escape(self.request.get('title'))
        new_listing.message = cgi.escape(self.request.get('message'))[0:500]
        hash_object = hashlib.md5(new_listing.message + new_listing.title)
        new_listing.post_id = hash_object.hexdigest()
        # new_listing.date = item['created_time']
        author_id = cgi.escape(self.request.get('author_id'))
        if author_id=="":
            author_id = "10200204025"   #default user
        new_listing.author_id = author_id
        author_name = cgi.escape(self.request.get('author_name'))
        if author_name=="":
            author_name = "cxz"
        new_listing.author_name = author_name
        new_listing.link_to_post = cgi.escape(self.request.get('link_to_post'))
        new_listing.category = cgi.escape(self.request.get('category'))
        # img = cgi.escape(self.request.get('picture'))
        # if not img == "":
        #     img = images.resize(img, 200, 200)
        new_listing.picture = cgi.escape(self.request.get('picture'))
        # avatar = self.request.get('img')
        # avatar = self.request.get('img')
        img = self.request.get('image_post')
        if img!="" and img is not None:
            new_listing.image_post = img #images.resize(img,200,200)
        new_listing.put()
        self.response.headers['Access-Control-Allow-Origin'] = '*'
        self.response.out.write('<html><head><meta http-equiv="refresh" content="0; url=http://104.236.227.17/thriftshop/main.php" /></head><body>You wrote:<pre>')
        self.response.out.write("post created")
        self.response.out.write('</pre></body></html>')

class AllPageHandler(webapp2.RequestHandler):
    def get(self):
        page_no = 1
        page_no = int(page_no)
        logging.debug("Page no received is " + str(page_no))
        result = Listing.query().order(-Listing.date);
        listings_list = []
        cnt = 0
        cont_count = 0
        # debug_string = []
        for listing in result:
            cnt = cnt + 1
            if cnt > (300 * (page_no - 1)) and cnt <= (300 * page_no):
                d = {}
                d['message'] = listing.message
                d['title'] = listing.title
                d['post_id'] = listing.post_id
                d['author_id'] = listing.author_id
                d['author_name'] = listing.author_name
                d['category'] = listing.category
                if listing.picture == "":
                    if listing.image_post is not None and listing.image_post != "":
                        d['picture'] = str("http://2.genuine-amulet-864.appspot.com/img?img_id=") + listing.key.urlsafe()
                d['picture'] = listing.picture
                d['date'] = str(listing.date)
                d['link_to_post'] = listing.link_to_post
                listings_list.append(d)
        self.response.headers['Access-Control-Allow-Origin'] = '*'
        js = json.dumps(listings_list)
        self.response.write(js)

class ItemHandler(webapp2.RequestHandler):
    def get(self,itemid):
        # self.response.write(itemid)
        res = Listing.query(Listing.post_id == itemid)
        listings_list = []
        if res.count() > 0:
            # self.response.write(res)
            for item in res:
                d = {}
                d['message'] = item.message
                d['title'] = item.title
                d['post_id'] = item.post_id
                d['author_id'] = item.author_id
                d['author_name'] = item.author_name
                d['category'] = item.category
                if listing.picture == "":
                    if listing.image_post is not None and listing.image_post != "":
                        d['picture'] = str("http://2.genuine-amulet-864.appspot.com/img?img_id=") + listing.key.urlsafe()
                d['picture'] = listing.picture
                d['date'] = str(item.date)
                d['link_to_post'] = item.link_to_post
                listings_list.append(d)
        js = json.dumps(listings_list)
        self.response.headers['Access-Control-Allow-Origin'] = '*'
        self.response.write(js) 

class commentsHandler(webapp2.RequestHandler):
    def get(self,post_id):
        # self.response.write(post_id)
        comment_url = "https://graph.facebook.com/v2.2/" + str(post_id) + "/comments?access_token=CAANI8ZBCAeOwBAHy59OJRb3B9y9X9aNn2XekTCjBsEWlR4H71M0srnqT4DJ6fnZBvPfilH8Nm4xXBYAZA3JwMqD5ElrlcptoNaEDZCRYtRTaPqhRqio7S6ioxTYXOT2ABANENj2mrHF6FNBv6et3X7hrbMzsIU8ZBK3YN5LlcNzAoQFpBB3HtNw354QdVggfLAemF4fzElS3nVRB6yOqE"
        # self.response.write(comment_url)
        json_response = urllib2.urlopen(comment_url)
        data = json.load(json_response)
        # debug_string += "Page no fetching is " + str(page_no) + "\n"
        comments_list = []
        for item in data['data']:
            d = {}
            d['message'] = item['message']
            d['comment_by'] = item['from']['name']
            d['created_time'] = item['created_time']
            d['author_id'] = item['from']['id']
            comments_list.append(d)
        js = json.dumps(comments_list)
        self.response.headers['Access-Control-Allow-Origin'] = '*'
        self.response.write(js)

class createuserHandler(webapp2.RequestHandler):
    def get(self,username):
        # if str(username).contains("@gatech.edu"):
            #Generate hash
        hash_object = hashlib.md5(username)
        hash_string = hash_object.hexdigest()
        sender_address = "GT Thrift Mobile Support<support@genuine-amulet-864.appspotmail.com>"
        subject = "GT Thrift - Password"
        res = Authenticate.query(Authenticate.username == str(username))
        body = ""
        if res.count() == 0:
            new_user = Authenticate(parent=guestbook_key(DEFAULT_GUESTBOOK_NAME))
            new_user.username = str(username)
            new_user.password = str(hash_string)
            new_user.put()
            body = """Your password to login to the system is %s""" % str(hash_string)
        else:
            first_item = None
            for item in res:
                first_item = item
                break
            password = first_item.password
            body = """Hi\nYour password to login to the GT Thrift Mobile system is %s""" % password
        
        user_address = str(username) + str("@gatech.edu")
        self.response.headers['Access-Control-Allow-Origin'] = '*'
        mail.send_mail(sender_address, user_address, subject, body)

class authenticateHandler(webapp2.RequestHandler):
    def post(self):
        username = cgi.escape(self.request.get('username'))
        password = cgi.escape(self.request.get('password'))
        res = Authenticate.query(Authenticate.username == str(username))
        first_item = None
        for item in res:
            first_item = item
            break
        self.response.headers['Access-Control-Allow-Origin'] = '*'
        password_db = first_item.password
        if str(password) == str(password_db):
            self.response.write(1)
        else:
            self.response.write(0)

class changePasswordHandler(webapp2.RequestHandler):
    def post(self):
        username = cgi.escape(self.request.get('username'))
        new_password = cgi.escape(self.request.get('newpassword'))
        res = Authenticate.query(Authenticate.username == str(username))
        first_item = None
        for item in res:
            first_item = item
            break
        first_item.password = new_password
        self.response.headers['Access-Control-Allow-Origin'] = '*'
        try:
            ret = first_item.put()
            self.response.write(1)
        except Exception, e:
            self.response.write(0)

app = webapp2.WSGIApplication([
    (r'/getlistings/(\d+)', PageHandler),
    (r'/getlistings/user/(.*)/(\d+)', UserHandler),
    (r'/getlistings/(.*)/(\d+)', CategoryHandler),
    (r'/search/(.*)/(\d+)', SearchHandler),
    (r'/getitem/(.*)',ItemHandler),
    ('/getalllistings/?',AllPageHandler),
    ('/deleteall/?',DeleteAllHandler),
    ('/updatedb/?',updatedbHandler),
    (r'/getcomments/(.*)',commentsHandler),
    ('/postlisting/?',PostListingHandler),
    (r'/createuser/(.*)',createuserHandler),
    ('/changepassword/?',changePasswordHandler),
    ('/img',Image),
    ('/authenticate/?',authenticateHandler)
], debug=True)
