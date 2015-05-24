#!/usr/bin/env python
# -*- coding: UTF-8 -*-
__author__ = "Scott Hendrickson, Josh Montague, Ryan Choi" 

import os
import sys
import re
import time
import requests
import json
import codecs
import datetime

import logging

reload(sys)
sys.stdout = codecs.getwriter('utf-8')(sys.stdout)
sys.stdin = codecs.getreader('utf-8')(sys.stdin)

# formatter of data from API 
TIME_FMT = "%Y%m%d%H%M"
PAUSE = 3  # seconds between page requests

class SearchClient(object):
    
    def __init__(self
            , user
            , password
            , stream_url
            ):
        #############################################
        # set up query paramters
        self.paged = False
        self.record_callback = None
        self.user = user
        self.password = password
        self.stream_url = stream_url

    def set_index(self, use_case, count_bucket):
        self.use_case = use_case
        if use_case.startswith("time"):
            if not self.stream_url.endswith("counts.json"): 
                self.stream_url = self.stream_url[:-5] + "/counts.json"
            if count_bucket not in ['day', 'minute', 'hour']:
                logging.error("Error. Invalid count bucket: %s \n" % str(count_bucket))
                sys.exit()

    def req(self):
        try:
            s = requests.Session()
            s.headers = {'Accept-encoding': 'gzip'}
            s.auth = (self.user, self.password)
            res = s.post(self.stream_url, data=json.dumps(self.rule_payload))
        except requests.exceptions.ConnectionError, e:
            logging.error("Error (%s). Exiting without results." % str(e))
            sys.exit()
        except requests.exceptions.HTTPError, e:
            logging.error("Error (%s). Exiting without results." % str(e))
            sys.exit()
        return res.text

    def parse_JSON(self):
        acs = []
        repeat = True
        page_count = 0
        total_count = 0
        while repeat:
            timing_start = datetime.datetime.now()
            doc = self.req()
            timing = datetime.datetime.now() - timing_start
            try:
                
                tmp_response = json.loads(doc)

                if "results" in tmp_response:
                    results = tmp_response["results"]
                    acs.extend(results)
                    logging.info("Gnip query %s records (%sms)" % (len(results), timing))

                if "error" in tmp_response:
                    logging.error("Error, invalid request")
                    logging.error("Query: %s" % self.rule_payload)
                    logging.error("Response: %s" % doc)
                    raise Exception(tmp_response["error"]["message"])
            except ValueError:
                logging.error("Error, results not parsable")
                logging.error(doc)
                sys.exit()

            repeat = False
            if self.paged:
                
                if len(acs) > 0:
                    if self.record_callback is not None:
                        results = tmp_response["results"]
                        self.record_callback(results, total_count)
                        total_count = total_count + len(results)
                else:
                    logging.info("no results returned for rule:{0}".format(str(self.rule_payload)))

                if "next" in tmp_response:
                    self.rule_payload["next"] = tmp_response["next"]
                    repeat = True
                    page_count += 1
                    logging.info("Fetching page {}...".format(page_count))
                else:
                    if "next" in self.rule_payload:
                        del self.rule_payload["next"]
                    repeat = False
                time.sleep(PAUSE)
                
        return acs

    def query(self
            , pt_filter
            , max_results=100
            , record_callback=None
            , use_case="wordcount"
            , start=None
            , end=None
            , count_bucket="day" 
            , query=False):

        self.set_index(use_case, count_bucket)
        
        if record_callback:
            self.record_callback = record_callback
            max_results = 500
            self.paged = True
        else:
            self.paged = False

        self.rule_payload = {
                        'query': pt_filter
                        , 'maxResults': int(max_results)
                        , 'publisher': 'twitter'
                        }
        
        if start:
            self.rule_payload["fromDate"] = start.strftime(TIME_FMT)
        if end:
            self.rule_payload["toDate"] = end.strftime(TIME_FMT)
            
        if use_case.startswith("time"):
            self.rule_payload["bucket"] = count_bucket
        if query:
            logging.error("API query:")
            logging.error(self.rule_payload)
            return 

        self.doc = []
        self.res_cnt = 0

        for rec in self.parse_JSON():
            self.res_cnt += 1
            if use_case.startswith("json"):
                self.doc.append(json.dumps(rec))
            elif use_case.startswith("tweets"):
                self.doc.append(rec)
            elif use_case.startswith("time"):
                self.doc.append(rec)

        return self.get_repr(pt_filter)

    def get_repr(self, pt_filter):
        WIDTH = 60
        res = [u"-"*WIDTH]
        if self.use_case.startswith("json"):
            res = self.doc
        elif self.use_case.startswith("tweets"):
            res = self.doc
            return res
        elif self.use_case.startswith("time"):
            res = [json.dumps({"results": self.doc})] 
        return "\n".join(res)

if __name__ == "__main__":
    g = SearchClient("USER"
            , "PASSWORD"
            , "STREAM_URL",
            )
    
    term = "captain america"
    
    print g.query_api(term)
    print g.query_api(term, 50)
    print g.query_api(term, 10, "json")
    print g.query_api(term, 10, "timeline")
    print g.query_api(term, 10, "tweets")
