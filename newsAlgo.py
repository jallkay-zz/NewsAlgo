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

stockNewsIndex = {}
initFunds = 25000.00

availableTickerFunds = {} # put amount of funds remaining in here 
shareTicker = {} # put num of shares owned per ticker in here

overrideData = True

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

def buildIndex(mainDF):
    for i in range(0, len(mainDF.values)):
        item = mainDF.values[i]
        try:
            for name, value in zip(mainDF.columns, item):
                if not type(value) == float:
                    if 'tag_' in name and not 'None' in value:
                        temp = ast.literal_eval(value)
                        print(temp)
                        if stockNewsIndex.get(temp['stockSymbol']):
                            stockNewsIndex[temp['stockSymbol']].append(item)
                        else:
                            stockNewsIndex[temp['stockSymbol']] = []
                            stockNewsIndex[temp['stockSymbol']].append(item)
        except:
            print("execption in building index")
                

#pull in news 
def getNews(firstRun = False):
    newsSources = [name[2].lower() for name in stockSymbols.values]
    cik = [name[7] for name in stockSymbols.values]
    print "getting news"
    noData = False
    try:
        mainDF = pandas.DataFrame.from_csv('data.csv')
    except:
        noData = True
    data = {}
    rawData = []
    alreadyThere = False
    count = 0

    threading.Timer(3600, getNews).start()
    if not noData and firstRun:
        buildIndex(mainDF)
        return mainDF


    for source, cik in zip(newsSources, cik):
        
        ciklen = len(str(int(cik))) 
        if not ciklen == 10:
            newcik = ""
            for i in range (0, 10-ciklen):
                newcik += "0"
        cik = newcik + str(cik)

        # 10-Q filings - to be ran only ever few weeks or during close times?
        #company = edgar.Company(source, cik)
        #tree = company.getAllFilings(filingType = "10-Q")
        #docs = edgar.getDocuments(tree, noOfDocuments=5)

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
                    for url in mainDF.url:
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
    
    if not noData:
        mainDF = mainDF.append(frame, ignore_index=True)
    else:
        mainDF = frame
    mainDF.to_csv('data.csv')
    firstRun = False
    buildIndex(mainDF)
    print "finished getting news"
    return mainDF

def composeTag(article):
    analysis = convert(getAnalysis(article))
    article['tags'] = ''.join(str(a) + ',' for a in analysis.keys())
    for name, desc in analysis.iteritems():
        tagDict = {}
        tagDict['desc'] = desc
        tagDict['name'] = name
        tagDict['stockSymbol'] = getStockSymbol(name)
        tagDict['type'] = 'Other'
        article['tag_' +  str(([i for i,x in enumerate(analysis.keys()) if x == name])[0])] = tagDict
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
    for name, value in zip(mainDF.columns, item):
        if 'tag_' in name:
            try:
                value = ast.literal_eval(value) if type(value) == str else value
            except Exception:
                print Exception
                continue
        if 'sentiment' in name:
            value = ast.literal_eval(value)
            del value['compound']
        if type(value) == float:
            value = "" if isnan(value) else value
        itemDict[name] = value
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
    for item in mainDF.values:
        itemDict = {}
        for name, value in zip(mainDF.columns, item):
            if type(value) == float:
                value = "" if isnan(value) else value
            itemDict[name] = value if not value == float('nan') else ""
        if itemDict['publishedAt']:
            updatedAt = datetime.strptime(itemDict['publishedAt'], '%Y-%m-%dT%H:%M:%SZ') if len(itemDict['publishedAt']) == 20 else datetime.strptime(itemDict['publishedAt'], '%Y-%m-%dT%H:%M:%S.%fZ')
            diff = datetime.utcnow() - updatedAt
            itemDict['updatedShort'] = 'Days: ' + str(diff.days) if diff.days else 'Secs: ' + str(diff.seconds) if diff.seconds < 60 else 'Mins: ' + str(diff.seconds / 60) if diff.seconds / 60 < 60 else 'Hours: ' + str(diff.seconds / 3600)
        itemDict['source'] = itemDict['url'].split('.')[1].upper()
        itemDict['id'] = counter
        counter = counter + 1
        output.append(itemDict)
    return jsonify(output)

@app.route('/json/detail/<int:mainID>')
def detail(mainID):
    returnData = mainDF.values[mainID]
    return jsonify(getDict(returnData))

@app.route('/json/detail/analysis/<int:mainID>')
def detailAnalysis(mainID):
    returnData = mainDF.values[mainID]
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

    
# @app.route('/json/mongo')
# def mongo():
#     records = json.loads(mainDF.T.to_json()).values()
#     db.myCollection.insert(records)
#     return "Successful"

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

        if stockNewsIndex.get(symbol):
            timestamps = [datetime.strptime(item[2], "%Y-%m-%dT%H:%M:%SZ") for item in stockNewsIndex.get(symbol)]

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
            output['label'][name]           = [stockNewsIndex.get(symbol)[timestamps.index(stamp)][14], name] if success else name
            output['pointStyle'][name]      = "circle"
            output['backgroundColor'][name] = 'rgb(193, 0, 0)' if success else 'rgb(225,225,225)'
            output['radius'][name]          = "8" if success else "1"
        return jsonify(output)


@app.route('/dashboard')
def index():
    return render_template('index.html', header="")

# ONLY USE WHEN YOURE OVERRITING THE CSV
@app.route('/json/all')
def getAllData():
    mainDict = []
    progress = 0
    for rawItem in mainDF.values:
        progress = progress + 1
        print 'progress: ' + str(progress)
        item = getDict(rawItem)
        mainDict.append(composeTag(item))
    
    frame = pandas.DataFrame.from_dict(mainDict)
    frame.to_csv('data.csv')
    return jsonify(mainDict)
    

if __name__ == "__main__":
    stockSymbols = pandas.DataFrame.from_csv('shortListedStocks.csv', header=0)
    splitTickerfunds()
    client = pymongo.MongoClient(uri)
    db = client.get_default_database()
    mainDF       = getNews(firstRun=True)
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
    


