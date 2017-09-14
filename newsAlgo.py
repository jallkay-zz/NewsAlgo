from flask import Flask, jsonify, render_template
from yahoo_finance import Share
from datetime import datetime, timedelta, date
import urllib, json
import threading
from alpha_vantage.timeseries import TimeSeries
import nltk
from numpy import isnan
import wikipedia as wiki
from collections import OrderedDict
import pandas


#init flask
app = Flask(__name__)

# newsApi stuff
newsApiKey  = '3e05eceb5b124303a021684e2152dcc5'
newsSources = ['the-wall-street-journal', 'the-economist', 'business-insider', 'bloomberg', 'bbc-news']

# stock quotes
ts = TimeSeries(key='YWBHDJPSFY0S9FHO')

redirects = {}
redirects['apple'] = 'Apple Inc.'
redirects['trumps'] = 'trump'

splits = [('.s', 'D'), ("'s", 'D'), ('Inc', 'K')]


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
def getNews():
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
    for source in newsSources:
        newsUrl     = ('http://newsapi.org/v1/articles?source=%s&sortBy=top&apiKey=' % source) + newsApiKey
        response    = urllib.urlopen(newsUrl)
        returned    = response.read()
        if returned:
            jsonconvert = json.loads(returned)
            converted   = convert(jsonconvert)
            
            for article in converted['articles']:
                count = count + 1
                print 'progress: ' + str(count)
                if not noData:
                    for url in mainDF.url:
                        if article['url'] == url:
                            alreadyThere = True
                            break
                    if not alreadyThere:
                        analysis = convert(getAnalysis(article))
                        article['tags'] = ''.join(str(a) + ',' for a in analysis.keys())
                        for item in analysis.values():
                            article['tag_' +  str(([i for i,x in enumerate(analysis.values()) if x == item])[0])] = item
                        rawData.append(article)
                else:
                    analysis = convert(getAnalysis(article))
                    article['tags'] = ''.join(str(a) + ',' for a in analysis.keys())
                    for item in analysis.values():
                        article['tag_' +  str(([i for i,x in enumerate(analysis.values()) if x == item])[0])] = item
                    rawData.append(article)

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
    threading.Timer(600, getNews).start()

    return mainDF


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
        if type(value) == float:
            value = "" if isnan(value) else value
        itemDict[name] = value
    return itemDict

def getAnalysis(newsArticle):
    wikiReturn    = {}
    finished      = False
    currentWord   = ''
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

@app.route('/json/headlines')
def headlines():
    output = []
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

@app.route('/json/stock/<type>/<symbol>')
def stock(type, symbol):
    if type == 'get_daily':
        # if the amount of articles on the subject goes back, do the full one 
        return jsonify(ts.get_daily(symbol))
    if type == 'get_intraday':
        output = {}
        #TODO change this back 
        core = ts.get_daily(symbol)
        for name, value in core[0].iteritems():
            
            output[name] = value["1. open"]
        return jsonify(output)


@app.route('/dashboard')
def index():
    return render_template('index.html', header="")
    

if __name__ == "__main__":
    mainDF = getNews()
    app.run(host='0.0.0.0')


