from flask import Flask, jsonify, render_template
from yahoo_finance import Share
from datetime import datetime, timedelta, date
import urllib, json
import threading
from alpha_vantage.timeseries import TimeSeries
import nltk
from nltk.sentiment.vader import SentimentIntensityAnalyzer as sentAnalysis
from nltk.tokenize import word_tokenize
import ast
from numpy import isnan
import wikipedia as wiki
from collections import OrderedDict
import pandas
import edgar
from math import floor
import os
import sys
import pymongo
import operator
from bson.objectid import ObjectId as ObjectId
from dateutil.relativedelta import relativedelta
import unicodedata

#init flask
app = Flask(__name__)

# newsApi stuff
newsApiKey  = '3e05eceb5b124303a021684e2152dcc5'
#newsSources = ['the-wall-street-journal', 'the-economist', 'business-insider', 'bloomberg', 'bbc-news']
uri = 'mongodb://jamesak:Lancaster1@ds261118.mlab.com:61118/heroku_glkl90f7'
# stock quotes
ts = TimeSeries(key='YWBHDJPSFY0S9FHO')

redirects = {}
redirects['apple'] = 'Apple Inc.'
redirects['trumps'] = 'trump'

stockSymbols = {}

initFunds = 25000.00

currentMessage = []
classifier = {}
mydictionary = {}

overrideData = True
gotQuarterly = False
splits = [('.s', 'D'), ("'s", 'D'), ('Inc', 'K')]

def splitTickerFunds():
    size = len(stockSymbols.values)
    stockobjs = list(db.stocks.find({}))
    if len(stockobjs) == size:
        for obj in stockobjs:
            obj['funds'] = initFunds / size
            obj['shares'] = 0
            db.stocks.update( { "_id" : obj['_id'] } , { "$set" : obj})
    else:
        db.stocks.delete_many({})
        for ticker in stockSymbols.values:
            stocks = {}
            stocks['ticker'] = ticker[0]
            stocks['funds'] = initFunds / size
            stocks['shares'] = 0
            db.stocks.insert(stocks)
    
def buyStock(ticker, price, shares):
    obj = db.stocks.find({ "ticker" : ticker })[0]
    availableFunds = obj['funds']
    requestedFunds = price * shares
    if requestedFunds < availableFunds:
        obj['funds'] -= requestedFunds
        obj['shares'] += shares
        db.stocks.update( { "_id" : obj['_id'] } , { "$set" : obj})
        currentMessage.append("BOUGHT %f of %s at %f amount available %f" % (shares, ticker, price, obj['funds']))
        return "BOUGHT %f of %s at %f amount available %f" % (shares, ticker, price, obj['funds'])
    else:
        return "NOT BOUGHT %f of %s at %f, insufficient funds. amount available %f" % (shares, ticker, price, obj['funds'])

    
def sellStock(ticker, price, shares):
    obj = db.stocks.find({ "ticker" : ticker })[0]
    availableFunds = obj['funds']
    investedShares  = obj['shares']
    requestedFunds = price * shares
    if investedShares >= shares:
        obj['funds'] += requestedFunds
        obj['shares'] -= shares
        db.stocks.update( { "_id" : obj['_id'] } , { "$set" : obj})
        currentMessage.append("SOLD %f of %s at %f amount available %f" % (shares, ticker, price, obj['funds']))
        return "SOLD %f of %s at %f amount available %f" % (shares, ticker, price, obj['funds'])
    else:
        return "NOT SOLD %f of %s at %f amount available %f, invested shares %i" % (shares, ticker, price, obj['funds'], obj['shares'])

def getStockSymbol(companyName):
    for name in stockSymbols.values:
        if companyName.lower() == name[1].lower() or companyName.lower() == name[2].lower():
            return name[0]
        elif companyName.lower() in name[2].lower():
            return name[0]

def getCompanyName(stockSymbol):
    for name in stockSymbols.values:
        if stockSymbol.lower() == name[0].lower():
            return name[2]

def convert(input):
    if isinstance(input, dict):
        return dict((convert(key), convert(value)) for key, value in input.iteritems())
    elif isinstance(input, list):
        return [convert(element) for element in input]
    elif isinstance(input, unicode):
        return input.encode('ascii', 'ignore')
    else:
        return input

def nextdoor(iterable):
    iterator = iter(iterable)
    prev_item = None
    current_item = next(iterator)  # throws StopIteration if empty.
    for next_item in iterator:
        yield (prev_item, current_item, next_item)
        prev_item = current_item
        current_item = next_item
    yield (prev_item, current_item, None)

def sellAllStock(date=None):
    dbItems = list(db.stocks.find({}))
    tickers = {}
    for obj in dbItems:
        tickers[obj['ticker']] = obj['shares']
    if date:
        stockPrices = {}
        stockTimes = {}
        for tic in tickers.iteritems():
            stockPrices[tic[0]] = ts.get_daily(tic[0], outputsize='full')
            stockTimes[tic[0]] = [datetime.strptime(name, "%Y-%m-%d") for name in stockPrices[tic[0]][0].iterkeys()]
            print("got daily stock prices for %s" % tic[0])
            pivot = datetime.strptime(date, "%Y-%m-%d")
            closest = min(stockTimes[tic[0]], key=lambda x: abs(x - pivot))
            key = closest.strftime("%Y-%m-%d")
            price = stockPrices[tic[0]][0][key]['1. open']
            myreturn = sellStock(tic[0], float(price), tic[1])
            print myreturn

def updateNewsObject(obj):
     obj['_id'] = ObjectId(obj['_id'])
     db.myCollection.update( { "_id" : obj['_id'] } , { "$set" : obj})
     print "Updated obj %s in news db" % obj['_id']

def updateQuarterlyObject(obj):
     obj['_id'] = ObjectId(obj['_id'])
     db.quaterly.update( { "_id" : obj['_id'] } , { "$set" : obj})
     print "Updated obj %s in quarterly db" % obj['_id']

def updateNewsTrainObject(obj):
    returnData = list(db.trainNews.find({"refid" : str(obj['_id'])}))
    if len(returnData) > 0:
        returnData = returnData[0]
        returnData['newSentiment'] = obj['newSentiment']
        db.trainNews.update( { "_id" : returnData['_id'] } , { "$set" : returnData})
        print "Amended obj %s in train news db" % returnData['_id']
    else:
        obj['refid'] = str(obj['_id'])
        del obj['_id']
        db.trainNews.insert(obj)
        print "Added obj %s to train news db" % obj['_id']

def updateQuarterlyTrainObject(obj):
    returnData = list(db.train10Q.find({"refid" : obj['_id']}))
    if len(returnData) > 0:
        returnData['newSentiment'] = obj['newSentiment']
        db.train10Q.update( { "_id" : returnData['_id'] } , { "$set" : returnData})
        print "Amended obj %s in train 10Q db" % returnData['_id']
    else:
        obj['refid'] = str(obj['_id'])
        del obj['_id']
        db.train10Q.insert(obj)
        print "Added obj %s to train 10Q db" % obj['_id']




def backtestData(periodStart, periodEnd, ticker=False, quarterly=False, sellAtEnd=True):

    stockPrices = {}
    stockTimes = {}
    if ticker == False or ticker == None:
        tickers = [name[0].upper() for name in stockSymbols.values]
    else:
        tickers = [ticker]


    if not quarterly:
        if ticker == False or ticker == None:
            data = list(db.myCollection.find({}))
            print("got all news data for evaluation")
        else:
            data = list(db.myCollection.find({ "$or": [ { "tag_0.stockSymbol" : ticker }, { "tag_1.stockSymbol" : ticker },
                                                    { "tag_2.stockSymbol" : ticker }, { "tag_3.stockSymbol" : ticker },
                                                    { "tag_4.stockSymbol" : ticker }, { "tag_5.stockSymbol" : ticker },
                                                    { "tag_6.stockSymbol" : ticker }, { "tag_7.stockSymbol" : ticker },
                                                    { "tag_8.stockSymbol" : ticker }, { "tag_9.stockSymbol" : ticker },
                                                    { "tag_10.stockSymbol" : ticker }]}))
            print("got all news data for evaluation - %s" % ticker)
    else:
        if ticker == False or ticker == None:
            data = list(db.quaterly.find({}))
            print("got all quarterly data for evaluation")
        else:
            data = list(db.quaterly.find({ "ticker" : ticker } ))
            print("got all quarterly data for evaluation - %s" % ticker)

    for tic in tickers:
        if (datetime.utcnow() - periodStart) > timedelta(weeks = 1):
            stockPrices[tic] = ts.get_daily(tic, outputsize='full')
            stockTimes[tic] = [datetime.strptime(name, "%Y-%m-%d") for name in stockPrices[tic][0].iterkeys()]
            print("got daily stock prices for %s" % tic)
        else:
            stockPrices[tic] = ts.get_intraday(tic, interval='15min', outputsize='full')
            stockTimes[tic] = [datetime.strptime(name, "%Y-%m-%d %H:%M:%S") for name in stockPrices[tic][0].iterkeys()]
            print("got intraday stock prices for %s" % tic)

    print("evaluating data")
    for obj in data:
        if obj.get('publishedAt') or obj.get('date'):
            if quarterly:
                pivot = datetime.strptime(obj['date'], "%Y-%m-%d")
            else:
                pivot = datetime.strptime(obj['publishedAt'], '%Y-%m-%dT%H:%M:%SZ') if len(obj['publishedAt']) == 20 else datetime.strptime(obj['publishedAt'], '%Y-%m-%dT%H:%M:%S.%fZ')
            if pivot >= periodStart and pivot <= periodEnd:
                
                ticker = ""
                for item, value in obj.iteritems():
                    if "tag_" in item:
                        if value:
                            if type(value) == unicode:
                                value = ast.literal_eval(value)
                            if value.get('stockSymbol') != "" and value.get('stockSymbol') and value.get('stockSymbol') in tickers:
                                ticker = value['stockSymbol']
                    
                    elif "ticker" in item:
                        ticker = value

                if ticker != "":
                    if ticker == "BRKA":
                        ticker = "BRK.A"
                if ticker and ticker != "":
                    closest = min(stockTimes[ticker], key=lambda x: abs(x - pivot))
                    if quarterly or (datetime.utcnow() - periodStart) > timedelta(weeks = 1):
                        key = closest.strftime("%Y-%m-%d")
                    else:
                        key = closest.strftime("%Y-%m-%d %H:%M:%S")
                    
                    stockPrice = stockPrices[ticker][0][key]['1. open']
                    
                    #if type(obj['sentiment']) == unicode:
                    #    obj['sentiment'] = ast.literal_eval(obj['sentiment'])

                    if str(obj['newSentiment']) == "pos":
                        sentiment = "pos"
                        print(buyStock(ticker, float(stockPrice), 5))
                    else:
                        sentiment = "neg"
                        print(sellStock(ticker, float(stockPrice), 5))
    if sellAtEnd:
        sellAllStock(periodEnd.strftime("%Y-%m-%d"))
    return "Completed"

def evaluateSentiment(periodStart, periodEnd, periodDiff, ticker=False, quarterly=False, scatter=False):
    evaluations = []
    if scatter: 
        evaluations = {}
        evaluations['pos'] = {}
        evaluations['neg'] = {}
    rangeData = []

    stockPrices = {}
    stockTimes = {}
    stockTimesEnd = {}

    counter = 0
    positive = 0
    negative = 0
    if ticker == False or ticker == None:
        tickers = [name[0].upper() for name in stockSymbols.values]
    else:
        tickers = [ticker]


    if not quarterly:
        if ticker == False or ticker == None:
            data = list(db.myCollection.find({}))
            print("got all news data for evaluation")
        else:
            data = list(db.myCollection.find({ "$or": [ { "tag_0.stockSymbol" : ticker }, { "tag_1.stockSymbol" : ticker },
                                                    { "tag_2.stockSymbol" : ticker }, { "tag_3.stockSymbol" : ticker },
                                                    { "tag_4.stockSymbol" : ticker }, { "tag_5.stockSymbol" : ticker },
                                                    { "tag_6.stockSymbol" : ticker }, { "tag_7.stockSymbol" : ticker },
                                                    { "tag_8.stockSymbol" : ticker }, { "tag_9.stockSymbol" : ticker },
                                                    { "tag_10.stockSymbol" : ticker }]}))
            print("got all news data for evaluation - %s" % ticker)
    else:
        if ticker == False or ticker == None:
            data = list(db.quaterly.find({}))
            print("got all quarterly data for evaluation")
        else:
            data = list(db.quaterly.find({ "ticker" : ticker } ))
            print("got all quarterly data for evaluation - %s" % ticker)

    for tic in tickers:
        if (datetime.utcnow() - periodStart) > timedelta(weeks = 1):
            stockPrices[tic] = ts.get_daily(tic, outputsize='full')
            stockTimes[tic] = [datetime.strptime(name, "%Y-%m-%d") for name in stockPrices[tic][0].iterkeys()]
            print("got daily stock prices for %s" % tic)
        else:
            stockPrices[tic] = ts.get_intraday(tic, interval='15min', outputsize='full')
            stockTimes[tic] = [datetime.strptime(name, "%Y-%m-%d %H:%M:%S") for name in stockPrices[tic][0].iterkeys()]
            print("got intraday stock prices for %s" % tic)

    print("evaluating data")
    for obj in data:
        
        if obj.get('publishedAt') or obj.get('date'):
            if quarterly:
                pivot = datetime.strptime(obj['date'], "%Y-%m-%d")
            else:
                pivot = datetime.strptime(obj['publishedAt'], '%Y-%m-%dT%H:%M:%SZ') if len(obj['publishedAt']) == 20 else datetime.strptime(obj['publishedAt'], '%Y-%m-%dT%H:%M:%S.%fZ')
            if pivot >= periodStart and pivot <= periodEnd:
                
                ticker = ""
                for item, value in obj.iteritems():
                    if "tag_" in item:
                        if value:
                            if type(value) == unicode:
                                value = ast.literal_eval(value)
                            if value.get('stockSymbol') != "" and value.get('stockSymbol') and value.get('stockSymbol') in tickers:
                                ticker = value['stockSymbol']
                    
                    elif "ticker" in item:
                        ticker = value

                if ticker != "":
                    if ticker == "BRKA":
                        ticker = "BRK.A"
                    
                    counter = counter + 1
    
                    if scatter:

                        for i in range(1, periodDiff):
                            closest = min(stockTimes[ticker], key=lambda x: abs(x - pivot))
                            if quarterly or (datetime.utcnow() - periodStart) > timedelta(weeks = 1):
                                key = closest.strftime("%Y-%m-%d")
                            else:
                                key = closest.strftime("%Y-%m-%d %H:%M:%S")

                            pivotEnd = pivot + timedelta(days = i)
                            closestEnd = min(stockTimes[ticker], key=lambda y: abs(y - pivotEnd))
                            if quarterly or (datetime.utcnow() - periodStart) > timedelta(weeks = 1):
                                keyEnd = closestEnd.strftime("%Y-%m-%d")
                            else:
                                keyEnd = closestEnd.strftime("%Y-%m-%d %H:%M:%S")

                            startPrice = stockPrices[ticker][0][key]['1. open']
                            endPrice   = stockPrices[ticker][0][keyEnd]['1. open']

                            # if type(obj['sentiment']) == unicode:
                            #     obj['sentiment'] = ast.literal_eval(obj['sentiment'])
                            # if obj['sentiment']['pos'] > obj['sentiment']['neg']:
                            #     sentiment = "pos"
                            # else:
                            #     sentiment = "neg"

                            sentiment = str(obj['newSentiment'])

                            scatterEnd = 'Day' + str(i) if len(str(i)) == 2 else 'Day 0' + str(i)
                            if endPrice > startPrice and sentiment == "pos":
                                if not evaluations['pos'].get(scatterEnd):
                                    evaluations['pos'][scatterEnd] = 0
                                evaluations['pos'][scatterEnd] += 1
                            elif endPrice < startPrice and sentiment == "neg": 
                                if not evaluations['pos'].get(scatterEnd):
                                    evaluations['pos'][scatterEnd] = 0
                                evaluations['pos'][scatterEnd] += 1
                            else:
                                if not evaluations['neg'].get(scatterEnd):
                                    evaluations['neg'][scatterEnd] = 0
                                evaluations['neg'][scatterEnd] += 1
                    else:

                        closest = min(stockTimes[ticker], key=lambda x: abs(x - pivot))
                        if quarterly or (datetime.utcnow() - periodStart) > timedelta(weeks = 1):
                            key = closest.strftime("%Y-%m-%d")
                        else:
                            key = closest.strftime("%Y-%m-%d %H:%M:%S")
                        
                        pivotEnd = pivot + timedelta(days = periodDiff)
                        closestEnd = min(stockTimes[ticker], key=lambda y: abs(y - pivotEnd))
                        if quarterly or (datetime.utcnow() - periodStart) > timedelta(weeks = 1):
                            keyEnd = closestEnd.strftime("%Y-%m-%d")
                        else:
                            keyEnd = closestEnd.strftime("%Y-%m-%d %H:%M:%S")

                        startPrice = stockPrices[ticker][0][key]['1. open']
                        endPrice   = stockPrices[ticker][0][keyEnd]['1. open']

                        sentiment = str(obj['newSentiment'])
                        if sentiment == "pos":
                            positive = positive + 1
                        elif sentiment == "neg":
                            negative = negative + 1
                        #if type(obj['sentiment']) == unicode:
                        #    obj['sentiment'] = ast.literal_eval(obj['sentiment'])
                        #if obj['sentiment']['pos'] > obj['sentiment']['neg']:
                        #    sentiment = "pos"
                        #    positive = positive + 1
                        #elif obj['sentiment']['pos'] == obj['sentiment']['neg']:
                        #    sentiment = "neu"
                        #else:
                        #    sentiment = "neg"
                        #    negative = negative + 1

                        if endPrice > startPrice and sentiment == "pos":
                            evaluations.append(True)
                        elif endPrice < startPrice and sentiment == "neg": 
                            evaluations.append(True)
                        else:
                            evaluations.append(False)
    print("finished evaluating data, returning")
    print "positive %i" % positive
    print "negative %i" % negative
    print "total    %i" % counter
    return evaluations
                

def getDates(tree, numOfDocs):
    dates = []

    if len(tree.body[11]) > 5: # Check if filings exist
        if len(tree.body[11][5][0]) -1 < numOfDocs: # Check if there are enough filings
            numOfDocs = len(tree.body[11][5][0]) -1
            print("Not enough docs to return, returning %i" % numOfDocs)
        for i in range(1, numOfDocs + 1):
            myDate = tree.body[11][5][0][i][3].text_content() # Pull date from DOM
            dates.append(myDate)
    
        return dates


def getQuaterly(override=False):
    #10-Q filings - to be ran only ever few weeks or during close times?
    newsSources = [name[2].lower() for name in stockSymbols.values]
    tickers = [name[0].upper() for name in stockSymbols.values]
    cik = [name[7] for name in stockSymbols.values]
    
    for source, cik, ticker in zip(newsSources, cik, tickers):
        if '.' in ticker:
            ticker = ticker.replace('.', '')
        ciklen = len(str(int(cik))) 
        if not ciklen == 10:
            newcik = ""
            for i in range (0, 10-ciklen):
                newcik += "0"
        cik = newcik + str(cik)
        
        company = edgar.Company(source, cik)
        tree = company.getAllFilings(filingType = "10-Q")
        dates = getDates(tree, 5)

        data = list(db.quaterly.find({ "ticker" : ticker }))
        trueCount = 0
        for report in data:
            if report['date'] in dates:
                trueCount += 1 
        if trueCount == len(dates) and not override:
            if not override:
                print("Already have all data for %s (length %i)" % (ticker, trueCount))
                continue
        else:
            docs = edgar.getDocuments(tree, noOfDocuments=5)
            papers = [''.join(doc) for doc in docs]
            papers = [unicodedata.normalize("NFKD", pap) for pap in papers]
            
            print("Got papers from %s %s" % (source, ticker))
            sentiments = [getNew10QSentiment(pap) for pap in papers]
            print("Got sentiments from %s %s" % (source, ticker))
            
            for d, s in zip(dates, sentiments):
                records = {}
                data = list(db.quaterly.find({ "ticker" : ticker, "date" : d}))
                if not len(data) > 0:
                    records["ticker"]    = ticker
                    records["date"]      = d
                    records["sentiment"] = s

                    print("adding record %s %s to quarterly db" % (d, ticker))
                    currentMessage.append("adding record %s %s to quarterly db" % (d, ticker))
                    db.quaterly.insert(records)
    currentMessage.append("added all records to quarterly db, amending flag to not run again")
    print("added all records to quarterly db, amending flag to not run again")
    gotQuarterly = True


def getNews(firstRun = False):
    newsSources = [name[2].lower() for name in stockSymbols.values]
    print "getting news"
    noData = False
    
    try:
        dbData = list(db.myCollection.find({}))
        dbUrls = [d['url'] for d in dbData]
    except:
        noData = True

    count = 0

    threading.Timer(3600, getNews).start()
    if not noData and firstRun:
        return

    if not gotQuarterly:
        getQuaterly()
         
    
    for source in newsSources:

        goBack = datetime.strftime(date.today() - timedelta(days = 5), "%Y-%m-%d")
        newsUrl     = ('https://newsapi.org/v2/everything?q=%s&from=%s&sortBy=popularity&sources=bloomberg,bbc-news,financial-times,reuters,fortune,financial-post&language=en&apiKey=' % (source, goBack)) + newsApiKey
        print("getting news from %s" % newsUrl)
        response    = urllib.urlopen(newsUrl)
        returned    = response.read()
        if returned:
            jsonconvert = json.loads(returned)
            converted   = convert(jsonconvert)
            
            for article in converted['articles']:
                myData = None
                count = count + 1
                print('news source: %s progress: %s' % (source.title(), str(count)))
                if not noData:
                    if not article['url'] in dbUrls:
                        myData = composeTag(article)
                else:
                    myData = composeTag(article)

                if myData:
                    print("added article from %s to data" % source)
                    db.myCollection.insert(myData)
                
    firstRun = False
    currentMessage.append("Finished updating news content, uploaded to db")
    print "Finished updating news content, uploaded to db"

def composeTag(article):
    analysis = convert(getAnalysis(article))
    article['tags'] = ''
    for name, desc in analysis.iteritems():
        tagDict = {}
        if getStockSymbol(name):
            stock = True
        else:
            stock = False
        tagDict['desc'] = desc if desc and stock else ""
        tagDict['name'] = name if name and stock else ""
        tagDict['stockSymbol'] = getStockSymbol(name) if getStockSymbol(name) else ""
        tagDict['type'] = 'Other'
        article['tag_' +  str(([i for i,x in enumerate(analysis.keys()) if x == name])[0])] = tagDict
        if stock:
            article['tags'] = article['tags'] + name + ','
    if len(analysis) < 10:
        for i in range(len(analysis), 11):
            article['tag_' + str(i)] = {}
            article['tag_' + str(i)]['desc'] = ""
            article['tag_' + str(i)]['name'] = ""
            article['tag_' + str(i)]['stockSymbol'] = ""
            article['tag_' + str(i)]['type'] = 'Other'
    if article.get('title') and article.get('description'):
        article['sentiment'] = getSentiment(article.get('title') + ' ' + article.get('description'))
        article['newSentiment'] = getNewSentiment(article.get('title') + ' ' + article.get('description'))
    
    return article


def callWiki(currentWord, wikiReturn):
    try:

        redirectedWord = redirects.get(currentWord.lower(), currentWord)
        wikiReturn[redirectedWord] = wiki.summary(redirectedWord, sentences=2)
        return wikiReturn
    except wiki.exceptions.DisambiguationError as e:
        if ' ' in currentWord:
            splitWord = currentWord.lower().split(' ')
            for word in splitWord:
                callWiki(word, wikiReturn)
        print e.options
        return wikiReturn
    except:
        return wikiReturn

def getDict(item):
    itemDict = {}
    tagCount = 0
    for name, value in item.iteritems():
        if 'tag_' in name:
            tagCount += 1
            try:
                value = ast.literal_eval(value) if type(value) == str else value
            except Exception:
                print Exception
                continue
        if 'sentiment' in name:
            if type(value) == unicode:
                value = ast.literal_eval(value)
            if type(value) == dict:
                del value['compound']
        if type(value) == float:
            value = "" if isnan(value) else value
        itemDict[name] = value
    itemDict['_id'] = str(itemDict['_id'])

    if tagCount < 10:
        for i in range(tagCount, 11):
            itemDict['tag_' + str(i)] = {}
            itemDict['tag_' + str(i)]['desc'] = ""
            itemDict['tag_' + str(i)]['name'] = ""
            itemDict['tag_' + str(i)]['stockSymbol'] = ""
            itemDict['tag_' + str(i)]['type'] = 'Other'
    return itemDict

def getAnalysis(newsArticle):
    wikiReturn    = {}
    finished      = False
    currentWord   = ''
    if newsArticle.get('title') and newsArticle.get('description'):
        #tokenised     = nltk.pos_tag(nltk.word_tokenize(newsArticle['title'].replace('-', ' ') + ' ' + newsArticle['description'].replace('-', ' ')))
        #tokeniseddict = OrderedDict( tokenised )
        mystring = str(newsArticle['title'].replace('-', ' ') + ' ' + newsArticle['description'].replace('-', ' '))
        tickers = {}
        for name in stockSymbols.values:
            tickers[name[2].lower()] = name[1]

        override = False
        for tic in tickers.iteritems():
            if tic[0].lower() in mystring.lower():
                currentWord = tic[1]
                override = True
                finished = True
        # for prev, item, next in nextdoor(tokenised):
        #     if override:
        #         finished = True
    
        #     elif item[1] == "NNP" or item[1] == "CC":
        #         for split in splits:
        #             if split[0] in item[0]:
        #                 currentWord += ' ' if currentWord <> '' else ''
        #                 currentWord += item[0]
        #                 if split[1] == 'D': 
        #                     currentWord = currentWord.split(split[0])[0]
        #                 finished = True
        #                 break
        #         if not finished:
        #             if currentWord == '':
        #                 if item[1] == "CC":
        #                     continue
        #                 else:
        #                     currentWord += ' ' if currentWord <> '' else ''
        #                     currentWord += item[0] 
        #                     finished = False
        #                     if next:
        #                         if next[1] <> "NNP" and next[1] <> "CC":
        #                             finished = True
        #             elif len(currentWord.lower()) > 1 and currentWord.lower() in [name[2].lower() for name in stockSymbols.values]: 
        #                 finished = True
        #                 break
        #             else: 
        #                 currentWord += ' ' if currentWord <> '' else ''
        #                 currentWord += item[0] 
        #                 finished = False
        #                 if next:
        #                     if next[1] <> "NNP" and next[1] <> "CC":
        #                         finished = True

        if finished:
            wikiReturn = { currentWord : 'Test' }
            currentWord = ''
            finished = False
            override = False
    return wikiReturn


def getSentiment(content):
    # Return a sentiment
    sid = sentAnalysis()
    sentiment = sid.polarity_scores(content)
    return sentiment

def getNewSentiment(context):
    str_features = {word.lower(): (word in word_tokenize(context.lower())) for word in mydictionary['news']}
    sentiment = classifier['news'].classify(str_features)

    return sentiment

def trainNewsSentiment(firstTime = False):
    if firstTime:
        print "delaying start of training sentiment"
        threading.Timer(600, trainNewsSentiment).start()
    else:
        print "starting training sentiment"
        data = list(db.trainNews.find({}))
        train = [(obj['title'] + ' ' + obj['description'], obj['newSentiment']) for obj in data]
        mydictionary['news'] = set(word.lower() for passage in train for word in word_tokenize(passage[0]))
        t = [({word: (word in word_tokenize(x[0])) for word in mydictionary}, x[1]) for x in train]
        classifier['news'] = nltk.NaiveBayesClassifier.train(t)
        print "Completed training sentiment"

def getNew10QSentiment(context):
    str_features = {word.lower(): (word in word_tokenize(context.lower())) for word in mydictionary['10Q']}
    sentiment = classifier['10Q'].classify(str_features)

    return sentiment

def train10QSentiment(firstTime = False):
    if firstTime:
        print "delaying start of training sentiment for 10Q"
        threading.Timer(600, train10QSentiment).start()
    else:
        print "starting training sentiment for 10Q"
        newsSources = [name[2].lower() for name in stockSymbols.values]
        tickers = [name[0].upper() for name in stockSymbols.values]
        cik = [name[7] for name in stockSymbols.values]
        myPapers = {}
        for source, cik, ticker in zip(newsSources, cik, tickers):
            if '.' in ticker:
                ticker = ticker.replace('.', '')
            ciklen = len(str(int(cik))) 
            if not ciklen == 10:
                newcik = ""
                for i in range (0, 10-ciklen):
                    newcik += "0"
            cik = newcik + str(cik)
            
            company = edgar.Company(source, cik)
            tree = company.getAllFilings(filingType = "10-Q")
            dates = getDates(tree, 5)

            data = list(db.quaterly.find({ "ticker" : ticker }))
            docs = edgar.getDocuments(tree, noOfDocuments=5)
            papers = [''.join(doc) for doc in docs]
            papers = [unicodedata.normalize("NFKD", pap) for pap in papers]
            myPapers[ticker] = [(date, paper) for date, paper in zip(dates, papers)]
            print("Got papers from %s %s" % (source, ticker))

        data = list(db.train10Q.find({}))
        for i, d in enumerate(data):
            for articleDate, article in myPapers[d['ticker']]:
                if articleDate == str(d['date']):
                    data[i]['article'] = article

        train = [(obj['article'], obj['newSentiment']) for obj in data]
        mydictionary['10Q'] = set(word.lower() for passage in train for word in word_tokenize(passage[0]))
        t = [({word: (word in word_tokenize(x[0])) for word in mydictionary}, x[1]) for x in train]
        classifier['10Q'] = nltk.NaiveBayesClassifier.train(t)
        print "Completed training sentiment for 10Q"



@app.route('/json/reset/tickerfunds')
def resetTickerFunds():
    splitTickerFunds()
    return jsonify("True")

@app.route('/json/headlines')
def headlines():
    output = []
    counter = 0
    data = list(db.myCollection.find({}))
    for item in data:
        itemDict = {}
        for name, value in item.iteritems():
            if type(value) == float:
                value = "" if isnan(value) else value
            if "tag_" in name and value == None or "tag_" in name and value == "":
                value = {}
                value['desc'] = ""
                value['name'] = ""
                value['stockSymbol'] = ""
                value['type'] = 'Other'
            elif "tag_" in name and not value == None or "tag_" in name and not value == '':
                if type(value) == unicode:
                    try:
                        value = ast.literal_eval(value)
                    except:
                        print value
                if value.get("stockSymbol") == None:
                    value['stockSymbol'] = ""
            elif not value:
                value = ""
            itemDict[name] = value if not value == float('nan') else ""
        if itemDict['publishedAt']:
            updatedAt = datetime.strptime(itemDict['publishedAt'], '%Y-%m-%dT%H:%M:%SZ') if len(itemDict['publishedAt']) == 20 else datetime.strptime(itemDict['publishedAt'], '%Y-%m-%dT%H:%M:%S.%fZ')
            diff = datetime.utcnow() - updatedAt
            itemDict['updatedShort'] = 'Days: ' + str(diff.days) if diff.days else 'Secs: ' + str(diff.seconds) if diff.seconds < 60 else 'Mins: ' + str(diff.seconds / 60) if diff.seconds / 60 < 60 else 'Hours: ' + str(diff.seconds / 3600)
        itemDict['source'] = itemDict['url'].split('.')[1].upper()
        itemDict['id'] = counter
        itemDict['_id'] = str(itemDict['_id'])
        counter = counter + 1
        output.append(itemDict)
    
    output.sort(key=operator.itemgetter('publishedAt'), reverse=True)

    return jsonify(output)


@app.route('/json/headlines/<filter>')
def headlinesFilter(filter):
    if filter == "stocks":
        data = list(db.myCollection.find({"$or": [{ "tag_0.stockSymbol": { "$exists": True, "$ne": "" } }, { "tag_1.stockSymbol": { "$exists": True, "$ne": "" } },
                                                  { "tag_2.stockSymbol": { "$exists": True, "$ne": "" } }, { "tag_3.stockSymbol": { "$exists": True, "$ne": "" } },
                                                  { "tag_4.stockSymbol": { "$exists": True, "$ne": "" } }, { "tag_5.stockSymbol": { "$exists": True, "$ne": "" } },
                                                  { "tag_6.stockSymbol": { "$exists": True, "$ne": "" } }, { "tag_7.stockSymbol": { "$exists": True, "$ne": "" } },
                                                  { "tag_8.stockSymbol": { "$exists": True, "$ne": "" } }, { "tag_9.stockSymbol": { "$exists": True, "$ne": "" } },
                                                  { "tag_10.stockSymbol": { "$exists": True, "$ne": "" } } ] }))
    else:
        data = list(db.myCollection.find({}))
    output = []
    counter = 0
    
    for item in data:
        itemDict = {}
        for name, value in item.iteritems():
            if type(value) == float:
                value = "" if isnan(value) else value
            if "tag_" in name and value == None:
                value = {}
                value['desc'] = ""
                value['name'] = ""
                value['stockSymbol'] = ""
                value['type'] = 'Other'
            elif "tag_" in name and not value == None:
                if type(value) == unicode:
                    value = ast.literal_eval(value)
                if value.get("stockSymbol") == None:
                    value['stockSymbol'] = ""
            elif not value:
                value = ""
            itemDict[name] = value if not value == float('nan') else ""
        if itemDict['publishedAt']:
            updatedAt = datetime.strptime(itemDict['publishedAt'], '%Y-%m-%dT%H:%M:%SZ') if len(itemDict['publishedAt']) == 20 else datetime.strptime(itemDict['publishedAt'], '%Y-%m-%dT%H:%M:%S.%fZ')
            diff = datetime.utcnow() - updatedAt
            itemDict['updatedShort'] = 'Days: ' + str(diff.days) if diff.days else 'Secs: ' + str(diff.seconds) if diff.seconds < 60 else 'Mins: ' + str(diff.seconds / 60) if diff.seconds / 60 < 60 else 'Hours: ' + str(diff.seconds / 3600)
        itemDict['source'] = itemDict['url'].split('.')[1].upper()
        itemDict['id'] = counter
        itemDict['_id'] = str(itemDict['_id'])
        counter = counter + 1
        output.append(itemDict)

    
    output.sort(key=operator.itemgetter('publishedAt'), reverse=True)

    return jsonify(output)

@app.route('/json/quarterly')
def quaterlyReports():
    data = list(db.quaterly.find({}))
    output = []
    for item in data:
        
        quarter = str(int((floor(float(item['date'].split('-')[1]) / 4))) + 1)
        year    = str(item['date'].split('-')[0])
        item['source'] = item['ticker']
        item['_id'] = str(item['_id'])
        item['id'] = item['_id']
        item['title'] = "Q" + quarter + " Report " + year
        item['updatedShort'] = "Q" + quarter + " " + year

        output.append(item)
    return jsonify(output)

@app.route('/json/detail/<mongoID>')
def detail(mongoID):
    returnData = list(db.myCollection.find({"_id" : ObjectId(mongoID)}))
    if len(returnData) > 0:
        returnData = returnData[0]
    else:
        returnData = db.quaterly.find({"_id" : ObjectId(mongoID)})[0]
        quarter = str(int((floor(float(returnData['date'].split('-')[1]) / 4))) + 1)
        year    = str(returnData['date'].split('-')[0])
        returnData['source'] = returnData['ticker']
        returnData['_id'] = str(returnData['_id'])
        returnData['id'] = returnData['_id']
        returnData['title'] = "Q" + quarter + " Report " + year
        returnData['updatedShort'] = "Q" + quarter + " " + year

    return jsonify(getDict(returnData))

@app.route('/json/detail/analysis/<mongoID>')
def detailAnalysis(mongoID):
    returnData = list(db.myCollection.find({"_id" : ObjectId(mongoID)}))
    if len(returnData) > 0:
        returnData = returnData[0]
    else:
        returnData = db.quaterly.find({"_id" : ObjectId(mongoID)})[0]
        quarter = str(int((floor(float(returnData['date'].split('-')[1]) / 4))) + 1)
        year    = str(returnData['date'].split('-')[0])
        company = getCompanyName(returnData['ticker'])
        returnData['source'] = company
        returnData['_id'] = str(returnData['_id'])
        returnData['id'] = returnData['_id']
        returnData['title'] = "Q" + quarter + " Report " + year
        returnData['updatedShort'] = "Q" + quarter + " " + year
        returnData['tag_0'] = { "name" : company, "stockSymbol" : returnData['ticker'] }
        returnData['tags'] = company + ','
        
    return jsonify(getDict(returnData))

@app.route('/json/messages')
def getMessages():
    if len(currentMessage) > 6:
        currentMessage.reverse()
        returnMessage = currentMessage[:5]
    else:
        returnMessage = currentMessage.reverse()
    return jsonify(returnMessage)

@app.route('/json/total')
def getTotal():
    dbItems = list(db.stocks.find({}))
    available = sum([obj['funds'] for obj in dbItems])
    shares = [obj['shares'] for obj in dbItems]
    tickers = [obj['ticker'] for obj in dbItems]
    #core = ts.get_batch_stock_quotes(tickers)
    #invested = sum([shares * float(value['2. price']) for value, shares in zip(core[0], shares)])

    total = available# + invested
    return jsonify("$" + str(total))

@app.route('/json/totalall')
def getAllTotal():
    output = {}
    dbItems = list(db.stocks.find({}))
    shares = [obj['shares'] for obj in dbItems]
    tickers = [obj['ticker'] for obj in dbItems]
    core = ts.get_batch_stock_quotes(tickers)
    invested = [share * float(value['2. price']) for value, share in zip(core[0], shares)]
    for name, i in zip(tickers, invested):
        output[name] = i 
    return jsonify(output)

@app.route('/json/<command>/<ticker>/<float:price>/<int:shares>')
def moveStock(command, ticker, price, shares):
    if command == "sell":
        response = sellStock(ticker, price, shares)
    elif command == "buy":
        response = buyStock(ticker, price, shares)
    print(response)
    return jsonify(response)

@app.route('/json/sellallstock/<date>')
def sellAllStockEndpoint(date):
    sellAllStock(date)
    return jsonify("True")

@app.route('/json/stock/<type>/<symbol>')
def stock(type, symbol):
    if type == 'get_daily':
        # if the amount of articles on the subject goes back, do the full one 
        
        return jsonify(ts.get_daily(symbol))
    if type == 'get_intraday':
        output = {}
        output['quote'] = {}
        output['pointStyle'] = {}
        output['label'] = {}
        output['backgroundColor'] = {}
        output['radius'] = {}
        success = False
        quarterlySuccess = False
        #TODO change this back 
        core = ts.get_intraday(symbol, interval='1min', outputsize='full')

        headlineData = list(db.myCollection.find({ "$or": [ { "tag_0.stockSymbol" : symbol }, { "tag_1.stockSymbol" : symbol },
                                                    { "tag_2.stockSymbol" : symbol }, { "tag_3.stockSymbol" : symbol },
                                                    { "tag_4.stockSymbol" : symbol }, { "tag_5.stockSymbol" : symbol },
                                                    { "tag_6.stockSymbol" : symbol }, { "tag_7.stockSymbol" : symbol },
                                                    { "tag_8.stockSymbol" : symbol }, { "tag_9.stockSymbol" : symbol },
                                                    { "tag_10.stockSymbol" : symbol }]}))

        rawQuarterlyData = list(db.quaterly.find({ "ticker" : symbol }))
        quarterlyData = []
        for item in rawQuarterlyData:
            quarter = str(int((floor(float(item['date'].split('-')[1]) / 4))) + 1)
            year    = str(item['date'].split('-')[0])
            item['source'] = item['ticker']
            item['_id'] = str(item['_id'])
            item['id'] = item['_id']
            item['title'] = "Q" + quarter + " Report " + year
            item['updatedShort'] = "Q" + quarter + " " + year
            quarterlyData.append(item)


        if len(headlineData) > 0:
            timestamps = [datetime.strptime(i['publishedAt'], "%Y-%m-%dT%H:%M:%SZ") for i in headlineData]
        else:
            timestamps = []
        if len(quarterlyData) > 0:
            quarterlyTimestamps = [datetime.strptime(i['date'], "%Y-%m-%d") for i in quarterlyData]
        else:
            quarterlyTimestamps = []
        for name, value in core[0].iteritems():
            priceTime = datetime.strptime(name, "%Y-%m-%d %H:%M:%S")
            if timestamps:
                for stamp in timestamps:
                    compare = priceTime - stamp if priceTime > stamp else stamp - priceTime
                    if timedelta(minutes = 7, seconds = 30) > compare:
                        success = True
                        break
                    else:
                        success = False
            if quarterlyTimestamps:
                for myStamp in quarterlyTimestamps:
                    compare = priceTime - myStamp if priceTime > myStamp else stamp - priceTime
                    if timedelta(hours = 24) > compare:
                        quarterlySuccess = True
                        break
                    else:
                        quarterlySuccess = False
                    
            if success:
                label = [headlineData[timestamps.index(stamp)]['title'], name]
                color = 'rgb(193, 0, 0)'
                radius = "8"
                del headlineData[timestamps.index(stamp)]
                del timestamps[timestamps.index(stamp)]

            elif quarterlySuccess:
                label = [quarterlyData[quarterlyTimestamps.index(myStamp)]['title'], name]
                color = 'rgb(0,0,0)'
                radius = "8"
                del quarterlyData[quarterlyTimestamps.index(myStamp)]
                del quarterlyTimestamps[quarterlyTimestamps.index(myStamp)]
            else:
                label = name
                color = 'rgb(225,225,225)'
                radius = "1"

            output['quote'][name]           = value["1. open"]
            output['label'][name]           = label
            output['pointStyle'][name]      = "circle"
            output['backgroundColor'][name] = color
            output['radius'][name]          = radius
        return jsonify(output)

@app.route('/json/evaluate/<periodStart>/<periodEnd>/<int:periodDiff>/<ticker>/<quarterly>/<scatter>')
def evaluateTicker(periodStart, periodEnd, periodDiff, ticker, quarterly, scatter):
    periodStart = datetime.strptime(periodStart, '%Y-%m-%d')
    periodEnd   = datetime.strptime(periodEnd, '%Y-%m-%d')
    quarterly = False if quarterly == "false" else True
    scatter = False if scatter == "false" else True
    if ticker == "ALL":
        evaluations = evaluateSentiment(periodStart, periodEnd, periodDiff, quarterly=quarterly, scatter=scatter)
    else:
        evaluations = evaluateSentiment(periodStart, periodEnd, periodDiff, ticker=ticker, quarterly=quarterly, scatter=scatter)
    
    return jsonify(evaluations)


@app.route('/json/backtest/<periodStart>/<periodEnd>/<ticker>/<quarterly>/<sellAtEnd>')
def runBacktestData(periodStart, periodEnd, ticker, quarterly, sellAtEnd):
    periodStart = datetime.strptime(periodStart, '%Y-%m-%d')
    periodEnd   = datetime.strptime(periodEnd, '%Y-%m-%d')
    quarterly = False if quarterly == "false" else True
    sellAtEnd = False if sellAtEnd == "false" else True
    if ticker == "ALL":
        returned = backtestData(periodStart, periodEnd, quarterly=quarterly, sellAtEnd=sellAtEnd)
    else:
        returned = backtestData(periodStart, periodEnd, ticker=ticker, quarterly=quarterly, sellAtEnd=sellAtEnd)
    return jsonify(returned)

@app.route('/dashboard')
def index():
    return render_template('index.html', header="")

# ONLY USE WHEN YOURE OVERRITING THE DB
@app.route('/json/all')
def getAllData():
    progress = 0
    data = list(db.myCollection.find({}))
    for rawItem in data:
        progress = progress + 1
        print 'progress: ' + str(progress)
        item = getDict(rawItem)
        myItem = composeTag(item)
        updateNewsObject(myItem)
    return "True"

@app.route('/json/10Q/all')
def getAll10QData():
    getQuaterly(override=True)
    return "True"

@app.route('/json/sentiment/<id>/<polarity>')
def updateSentimentObject(id, polarity):
    # Update existing object
    returnData = list(db.myCollection.find({"_id" : ObjectId(id)}))
    if len(returnData) > 0:
        returnData = returnData[0]
        returnData['newSentiment'] = polarity
        updateNewsObject(returnData)
        updateNewsTrainObject(returnData)
    else:
        returnData = db.quaterly.find({"_id" : ObjectId(id)})[0]
        returnData['newSentiment'] = polarity
        updateQuarterlyObject(returnData)
        updateQuarterlyTrainObject(returnData)

    return "True"


if __name__ == "__main__":
    stockSymbols = pandas.DataFrame.from_csv('shortListedStocks.csv', header=0)
    client = pymongo.MongoClient(uri)
    db = client.get_default_database()
    getNews(firstRun = True)
    trainNewsSentiment(firstTime = True)
    train10QSentiment(firstTime = True)
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
    


