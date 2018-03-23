from flask import Flask, jsonify, render_template
from yahoo_finance import Share
from datetime import datetime, timedelta, date
import urllib, json
import threading
from alpha_vantage.timeseries import TimeSeries
import nltk
from nltk.sentiment.vader import SentimentIntensityAnalyzer as sentAnalysis
import ast
from numpy import isnan
import wikipedia as wiki
from collections import OrderedDict
import pandas
import edgar
import os
import sys
import pymongo
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

availableTickerFunds = {} # put amount of funds remaining in here 
shareTicker = {} # put num of shares owned per ticker in here

overrideData = True
gotQuarterly = False
splits = [('.s', 'D'), ("'s", 'D'), ('Inc', 'K')]

def splitTickerfunds():
    size = len(stockSymbols.values)
    for ticker in stockSymbols.values:
        availableTickerFunds[ticker[0]] = initFunds / size
        shareTicker[ticker[0]] = 0
    
def buyStock(ticker, price, shares):
    availableFunds = availableTickerFunds[ticker]
    requestedFunds = price * shares
    if requestedFunds < availableFunds:
        availableTickerFunds[ticker] -= requestedFunds
        shareTicker[ticker] += shares
        return "BOUGHT %f of %s at %f amount available %f" % (shares, ticker, price, availableTickerFunds[ticker])
    
def sellStock(ticker, price, shares):
    availableFunds = availableTickerFunds[ticker]
    investedShares  = shareTicker[ticker]
    requestedFunds = price * shares
    if investedShares >= shares:
        availableTickerFunds[ticker] += requestedFunds
        shareTicker[ticker] -= shares
        return "SOLD %f of %s at %f amount available %f" % (shares, ticker, price, availableTickerFunds[ticker])

def getStockSymbol(companyName):
    for name in stockSymbols.values:
        if companyName.lower() == name[1].lower() or companyName.lower() == name[2].lower():
            return name[0]
        elif companyName.lower() in name[2].lower():
            return name[0]

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

#pull in news 

def getDates(tree, numOfDocs):
    dates = []

    if len(tree.body[11]) > 5: # Check if filings exist
        if len(tree.body[11][5][0]) -1 < numOfDocs: # Check if there are enough filings
            numOfDocs = len(tree.body[11][5][0]) -1
            print("Not enough docs to return, returning %i" % numOfDocs)
        for i in range(1, numOfDocs + 1):
            myDate = tree.body[11][5][0][i][3].text_content() # Pull date from DOM
            print myDate
            dates.append(myDate)
        # if paper[10] == '-': # FACEBOOK
        #     myDate = paper[11:19].replace('x', '')
        #     if len(myDate) == 7:
        #         myDate = "0" + myDate
        #     dateFull = datetime.strptime(myDate, "%m%d%Y").strftime("%Y%m%d")
        # elif paper[16] == "_": # MICROSOFT, SNAP, TESLA
        #     dateFull = paper[17:25] 

        # elif paper[8:14] == "xom10q": # EXXON MOBIL
        #     month = str(3 * int(paper[14]))
        #     month = "0" + month if len(month) == 1 else month
        #     year = paper[16:20]
        #     day = "30"
        #     dateFull = year + month + day
        # elif paper[8:12] == "corp": # JP Morgan
        #     month = str(3 * int(paper[13]))
        #     month = "0" + month if len(month) == 1 else month
        #     year = paper[14:18]
        #     day = "30"
        #     dateFull = year + month + day
        # else: # fallback to previous date - 3 months
        #     dateFull = (datetime.strptime(dateFull, "%Y%m%d") - relativedelta(months =+3)).strftime("%Y%m%d")

    
        return dates

def getQuaterly():
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
        docs = edgar.getDocuments(tree, noOfDocuments=5)
        papers = [''.join(doc) for doc in docs]
        papers = [unicodedata.normalize("NFKD", pap) for pap in papers]
        dates = getDates(tree, 5)
        print("Got papers from %s %s" % (source, ticker))
        sentiments = [getSentiment(pap) for pap in papers]
        print("Got sentiments from %s %s" % (source, ticker))
        
        for d, s in zip(dates, sentiments):
            records = {}
            data = list(db.quaterly.find({ "ticker" : ticker, "date" : d}))
            if not len(data) > 0:
                records["ticker"]    = ticker
                records["date"]      = d
                records["sentiment"] = s

                print("adding record %s %s to quarterly db" % (d, ticker))
                db.quaterly.insert(records)
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
    data = {}
    rawData = []
    alreadyThere = False
    count = 0

    threading.Timer(3600, getNews).start()
    if not noData and firstRun:
        return

    if not gotQuarterly:
        getQuaterly()

    for source in newsSources:

        goBack = datetime.strftime(date.today() - timedelta(days = 5), "%Y-%m-%d")
        newsUrl     = ('https://newsapi.org/v2/everything?q=%s&from=%s&sortBy=popularity&sources=bloomberg,bbc-news,financial-times,reuters,fortune,financial-post&language=en&apiKey=' % (source, goBack)) + newsApiKey
        response    = urllib.urlopen(newsUrl)
        returned    = response.read()
        if returned:
            jsonconvert = json.loads(returned)
            converted   = convert(jsonconvert)
            
            for article in converted['articles']:
                count = count + 1
                print('news source: %s progress: %s' % (source.title(), str(count)))
                if not noData:
                    for url in dbUrls:
                        if article['url'] == url:
                            alreadyThere = True
                            break
                    if not alreadyThere:
                        rawData.append(composeTag(article))
                else:
                    rawData.append(composeTag(article))

    for i in range(len(rawData)):
        for name, value in rawData[i].iteritems():
            if not data.get(name):
                data[name] = {}
            #add source
            data[name][i] = value
            
    frame = pandas.DataFrame.from_dict(data)
    records = json.loads(frame.T.to_json()).values()
    db.myCollection.insert(records)
    firstRun = False
    print "finished getting news, and uploaded to db"

def composeTag(article):
    analysis = convert(getAnalysis(article))
    article['tags'] = ''.join(str(a) + ',' for a in analysis.keys())
    for name, desc in analysis.iteritems():
        tagDict = {}
        tagDict['desc'] = desc if desc else ""
        tagDict['name'] = name if name else ""
        tagDict['stockSymbol'] = getStockSymbol(name) if getStockSymbol(name) else ""
        tagDict['type'] = 'Other'
        article['tag_' +  str(([i for i,x in enumerate(analysis.keys()) if x == name])[0])] = tagDict

    if len(analysis) < 10:
        for i in range(analysis, 11):
            article['tag_' + str(i)] = {}
            article['tag_' + str(i)]['desc'] = ""
            article['tag_' + str(i)]['name'] = ""
            article['tag_' + str(i)]['stockSymbol'] = ""
            article['tag_' + str(i)]['type'] = 'Other'
    article['sentiment'] = getSentiment(article['title'] + ' ' + article['description'])
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
        tokenised     = nltk.pos_tag(nltk.word_tokenize(newsArticle['title'].replace('-', ' ') + ' ' + newsArticle['description'].replace('-', ' ')))
        tokeniseddict = OrderedDict( tokenised )
        for prev, item, next in nextdoor(tokenised):
            if item[1] == "NNP" or item[1] == "CC":
                for split in splits:
                    if split[0] in item[0]:
                        currentWord += ' ' if currentWord <> '' else ''
                        currentWord += item[0]
                        if split[1] == 'D': 
                            currentWord = currentWord.split(split[0])[0]
                        finished = True
                        break
                if not finished:
                    if currentWord == '':
                        if item[1] == "CC":
                            continue
                        else:
                            currentWord += ' ' if currentWord <> '' else ''
                            currentWord += item[0] 
                            finished = False
                            if next:
                                if next[1] <> "NNP" and next[1] <> "CC":
                                    finished = True
                    elif currentWord.lower() in [name[2].lower() for name in stockSymbols.values]: 
                        finished = True
                        break
                    else: 
                        currentWord += ' ' if currentWord <> '' else ''
                        currentWord += item[0] 
                        finished = False
                        if next:
                            if next[1] <> "NNP" and next[1] <> "CC":
                                finished = True

            if finished:
                wikiReturn = callWiki(currentWord, wikiReturn)
                currentWord = ''
                finished = False
    return wikiReturn


def getSentiment(content):
    # Return a sentiment
    sid = sentAnalysis()
    sentiment = sid.polarity_scores(content)
    return sentiment

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
    return jsonify(output)


@app.route('/json/headlines/<filter>')
def headlinesFilter(filter):
    if filter == "stocks":
        data = list(db.myCollection.find({"$or": [{ "tag_0.stockSymbol": { "$exists": True, "$ne": None } }, { "tag_1.stockSymbol": { "$exists": True, "$ne": None } },
                                                  { "tag_2.stockSymbol": { "$exists": True, "$ne": None } }, { "tag_3.stockSymbol": { "$exists": True, "$ne": None } },
                                                  { "tag_4.stockSymbol": { "$exists": True, "$ne": None } }, { "tag_5.stockSymbol": { "$exists": True, "$ne": None } },
                                                  { "tag_6.stockSymbol": { "$exists": True, "$ne": None } }, { "tag_7.stockSymbol": { "$exists": True, "$ne": None } },
                                                  { "tag_8.stockSymbol": { "$exists": True, "$ne": None } }, { "tag_9.stockSymbol": { "$exists": True, "$ne": None } },
                                                  { "tag_10.stockSymbol": { "$exists": True, "$ne": None } } ] }))
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
    return jsonify(output)

@app.route('/json/detail/<mongoID>')
def detail(mongoID):
    returnData = db.myCollection.find({"_id" : ObjectId(mongoID)})[0]
    return jsonify(getDict(returnData))

@app.route('/json/detail/analysis/<mongoID>')
def detailAnalysis(mongoID):
    returnData = db.myCollection.find({"_id" : ObjectId(mongoID)})[0]
    return jsonify(getDict(returnData))

@app.route('/json/total')
def getTotal():
    available = sum(availableTickerFunds.values())
    core = ts.get_batch_stock_quotes(shareTicker.keys())
    invested = sum([shares * float(value['2. price']) for value, shares in zip(core[0], shareTicker.values())])

    total = available + invested
    return jsonify("$" + str(total))

@app.route('/json/totalall')
def getAllTotal():
    output = {}
    core = ts.get_batch_stock_quotes(shareTicker.keys())
    invested = [shares * float(value['2. price']) for value, shares in zip(core[0], shareTicker.values())]
    for name, i, j in zip(availableTickerFunds.keys(), availableTickerFunds.values(), invested):
        output[name] = i + j 
    return jsonify(output)

@app.route('/json/<command>/<ticker>/<float:price>/<int:shares>')
def moveStock(command, ticker, price, shares):
    if command == "sell":
        response = sellStock(ticker, price, shares)
    elif command == "buy":
        response = buyStock(ticker, price, shares)
    print(response)
    return jsonify(response)

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
        #TODO change this back 
        core = ts.get_intraday(symbol, interval='1min', outputsize='full')

        data = list(db.myCollection.find({ "$or": [ { "tag_0.stockSymbol" : symbol }, { "tag_1.stockSymbol" : symbol },
                                                    { "tag_2.stockSymbol" : symbol }, { "tag_3.stockSymbol" : symbol },
                                                    { "tag_4.stockSymbol" : symbol }, { "tag_5.stockSymbol" : symbol },
                                                    { "tag_6.stockSymbol" : symbol }, { "tag_7.stockSymbol" : symbol },
                                                    { "tag_8.stockSymbol" : symbol }, { "tag_9.stockSymbol" : symbol },
                                                    { "tag_10.stockSymbol" : symbol }]}))
        if len(data) > 0:
            timestamps = [datetime.strptime(i['publishedAt'], "%Y-%m-%dT%H:%M:%SZ") for i in data]

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
                    

            output['quote'][name]           = value["1. open"]
            output['label'][name]           = [data[timestamps.index(stamp)]['title'], name] if success else name
            output['pointStyle'][name]      = "circle"
            output['backgroundColor'][name] = 'rgb(193, 0, 0)' if success else 'rgb(225,225,225)'
            output['radius'][name]          = "8" if success else "1"
        return jsonify(output)


@app.route('/dashboard')
def index():
    return render_template('index.html', header="")

# ONLY USE WHEN YOURE OVERRITING THE CSV
# @app.route('/json/all')
# def getAllData():
#     mainDict = []
#     progress = 0
#     for rawItem in mainDF.values:
#         progress = progress + 1
#         print 'progress: ' + str(progress)
#         item = getDict(rawItem)
#         mainDict.append(composeTag(item))
    
#     frame = pandas.DataFrame.from_dict(mainDict)
#     frame.to_csv('data.csv')
#     return jsonify(mainDict)
    

if __name__ == "__main__":
    stockSymbols = pandas.DataFrame.from_csv('shortListedStocks.csv', header=0)
    splitTickerfunds()
    client = pymongo.MongoClient(uri)
    db = client.get_default_database()
    getNews(firstRun = True)
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
    


