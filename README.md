# AK Capital Documentation

Documentation provided here is related to the application hosted at http://akcapital.herokuapp.com/dashboard

# Backend API

The API is for use in connecting the backend to the frontend, and therefore is unathenticated due to the scope of the project. 
It allows for direct interaction with the backend, and should be used with extreme caution when sending commands that can permanently affect backend operation. 

All major endpoints are listed below, with an example usage and return

All returns are provided in JSON format, and are prefixed on the server (http://akcapital.herokuapp.com/json/...)

## Data retrieval endpoints
These endpoints are **relatively safe**, and do not perform any lasting effects on the backend

### Headlines 
**Endpoint** : `/json/headlines/`

**Usage** : This endpoint will return all headlines that are currently stored from the beggining of time on the Database, its specific usage within the web app is to popuilate the *Headlines* widget with data, so the amount of returning data is extremely large. 

**Latency** : Slow - Allow for 3-5 seconds for a return (Due to the amount data being retrieved on the backend)

**Return** : The return for this endpoint is a dump from the MongoDB database on the backend, so provides ID's to the db, and a very long list of data (a partial return from one of these objects is shown below.
```javascript
{
    "_id": "5abd13b8bee0e100041451fb", 
    "author": "Reuters Editorial", 
    "description": "DUBAI, March 29 (Reuters) - Qatar Petroleum and its partners won bids for four exploration blocks in the Campos basin off Brazil's Rio de Janeiro coast on Thursday, the company said in a statement.", 
    "id": 2193, 
    "publishedAt": "2018-03-29T15:49:32Z", 
    "sentiment": {
      "compound": 0.8126, 
      "neg": 0.076, 
      "neu": 0.7, 
      "pos": 0.224
    }, 
    "source": "REUTERS", 
    "tag_0": {
      "desc": "Qatar Petroleum (QP) is a state owned petroleum company in Qatar. The company operates all oil and gas activities in Qatar, including exploration, production, refining, transport, and storage.", 
      "name": "Qatar Petroleum", 
      "stockSymbol": "", 
      "type": "Other"
    },
    "tag_1" : {
    .....
```


### Company-Filtered Headlines 
**Endpoint** : `/json/headlines/<filter>`

**Usage** : To be used to filter the headline data to only include news articles that have a company detected that is on the portolio list. Used in the web app under the settings menu of the *Headlines* widget, allowing for an easier view of the data.

**Latency** : 1-2 Seconds

**Return** : Similar to the Headlines return, however only including objects that have at least one tag that has a valid stockSymbol.
``` javascript
{
    "_id": "5abcf8b9519923000421ccb8", 
    "author": "Giles Turner, Nate Lanxon", 
    "description": "Facebook Inc. pays female staff in Britain just 0.8 percent less on average than male employees, but womens' bonuses are almost 40 percent lower.", 
    "id": 2188, 
    "publishedAt": "2018-03-29T13:08:55Z", 
    "sentiment": {
      "compound": 0.564, 
      "neg": 0.09, 
      "neu": 0.753, 
      "pos": 0.157
    }, 
    "source": "BLOOMBERG", 
    "tag_0": {
      "desc": "Facebook is an American online social media and social networking service company based in Menlo Park, California. Its website was launched on February 4, 2004, by Mark Zuckerberg, along with fellow Harvard College students and roommates, Eduardo Saverin, Andrew McCollum, Dustin Moskovitz, and Chris Hughes.", 
      "name": "Facebook", 
      "stockSymbol": "FB", 
      "type": "Other"
    }, 
    "tag_1": {
      "desc": "", 
      "name": "", 
      "stockSymbol": "", 
      "type": "Other"
    }, 
```

### Quaterly Reports 
**Endpoint** : `/json/quarterly/`

**Usage** : To be used for displaying 10-Q Quarterly reports for the comapnies on the portfolio list, Used in the web-app under the settings filter 'Show Quarterly Reports'

**Latency** : <0.5 seconds

**Return** : The return displays a similar in structure dict to the headlines one, with some fields omitted:
```javascript
{
    "_id": "5ab4ff1aac466a00044d42d7", 
    "date": "2017-08-03", 
    "id": "5ab4ff1aac466a00044d42d7", 
    "sentiment": {
      "compound": 1.0, 
      "neg": 0.038, 
      "neu": 0.815, 
      "pos": 0.147
    }, 
    "source": "UPS", 
    "ticker": "UPS", 
    "title": "Q3 Report 2017", 
    "updatedShort": "Q3 2017"
},
```

### Article/Report Detail 
**Endpoint** : `/json/detail/<id>`

**Usage** : To be used for getting a specific ID's data (i.e. a specific news article) - The data returned back will provide significant data on general facts about the article, publish time, sentiment analysis ect.

**Latency** : < 100ms - Extremely quick

**Return** 
``` javascript
{
  "_id": "5ab4ff1aac466a00044d42d8", 
  "date": "2017-05-04", 
  "id": "5ab4ff1aac466a00044d42d8", 
  "sentiment": {
    "neg": 0.041, 
    "neu": 0.808, 
    "pos": 0.151
  }, 
  "source": "UPS", 
  "tag_0": {
    "desc": "", 
    "name": "", 
    "stockSymbol": "", 
    "type": "Other"
  }, 
  "tag_1": {
    "desc": "", 
    "name": "", 
    "stockSymbol": "", 
    "type": "Other"
  },   
```
### Article/Report Analysis 
**Endpoint** : `/json/detail/analysis/<id>`

**Usage** : Similarly to the Detail API call, however provides more specific information about the sentiment and content - To be used in the web app for displaying sentiment graphs, and the tag information

**Latency** : <100ms

**Return** : 
```javascript
{
  "_id": "5ab4ff1aac466a00044d42d8", 
  "date": "2017-05-04", 
  "id": "5ab4ff1aac466a00044d42d8", 
  "sentiment": {
    "neg": 0.041, 
    "neu": 0.808, 
    "pos": 0.151
  }, 
  "source": "UPS", 
  "tag_0": {
    "name": "UPS", 
    "stockSymbol": "UPS"
  }, 
  "tags": "UPS,", 
  "ticker": "UPS", 
  "title": "Q2 Report 2017", 
  "updatedShort": "Q2 2017"
}

```
### Backend Messages 
**Endpoint** : `json/messages`

**Usage** : To be used for getting access to the messages that have been published from the backend. These can vary from adding data to the database, to buying an selling stock. 

**Latency** : <100ms

**Return** : 
```javascript
{ 
    "BOUGHT 100 MSFT at 94.21",
    "SOLD 82 FB at 82.43"
}
```
### Itemised Portfolio Total 
**Endpoint** : `json/total`

**Usage** : Used for displaying the itemised total current values for all of the companies in the portofolio list. This takes into account cash available for each company, and the current value of the stock held.

**Latency**: <500ms - Slightly longer due to the calls to DB, and AlphaVantage

**Return**: 
```javascript
{ 
  "FB" : 1024.23,
  "MSFT" : 983.12,
  "MT" : 1832.12
  ...
}
```
### Portfolio Total 
**Endpoint** : `json/totalall`

**Usage** : Used for calculating the current value of all of the items in the portfolio combined, giving one figure. Used in the web app for the main portolio value at the top of the screen.

**Latency** : <500ms - Same issue as portfolio total

**Return** : 

```javascript
"$25000.0"
```

### Enriched Stock Price 
**Endpoint** : `json/stock/<type>/<ticker>`

**Usage** : Provides an extremely large amount of data for generating the graph shown in the web app, has news article data interweaved in with the labels for the data, and options for setting the colors and size of the data points on it. Also, it contains the stock quotes.

**Latency** : <5s, very costly procedure, and in involves several API calls

**Return** :
```javascript
{
  "backgroundColor": {
    "2018-03-16 09:30:00": "rgb(225,225,225)", 
    "2018-03-16 09:31:00": "rgb(225,225,225)", 
    "2018-03-16 09:32:00": "rgb(225,225,225)"
   }, 
  "label": {
    "2018-03-16 09:30:00": "2018-03-16 09:30:00", 
    "2018-03-16 09:31:00": "2018-03-16 09:31:00", 
    "2018-03-16 12:30:00": [
      "Retail's Middle Ground Is a Dangerous Place", 
      "2018-03-16 12:30:00"
    ], 
  }, 
  "pointStyle": {
    "2018-03-16 09:30:00": "circle", 
    "2018-03-16 09:31:00": "circle", 
    "2018-03-16 09:32:00": "circle", 
  },
  "quote": {
    "2018-03-16 09:30:00": "184.4900", 
    "2018-03-16 09:31:00": "184.4900", 
    "2018-03-16 09:32:00": "184.4500", 
  },
  "radius": {
    "2018-03-16 09:30:00": "1", 
    "2018-03-16 09:31:00": "1", 
    "2018-03-16 09:32:00": "8", 
   }
}
```

### Evaluate Performance (Whole Portfolio) 
**Endpoint** : `/json/evaluate/<periodStart>/<periodEnd>/<periodDiff>`

**Usage** : Used for evaluating the relationship between sentiment analysis sway (positive or negative) to the results of the stock price change over a user defined peroid (periodDiff - **accepted in D format**). This evaluates across the whole portfolio. Takes parameters periodStart **(accepted in YYYY-MM-DD format for both)** and periodEnd, for the period you want to evaluate against **(This usually is up to a maximum of 1 1/2 weeks beind today, as it takes intraday data - limitations of the AlphaVantage API)** 

**Latency** : Up to 30s, can take a long time due to the huge amount of data it has to process on the backend.

**Return** : Returns a true/false whether the sentiment analysis on that article successfully predicted that the stock price would go up/down in + periodDiff days
```javascript
{ 
    true, 
    false,
    true,
    true, 
    true, 
    false
}
```


### Evaluate Performance (Specific Company) 
**Endpoint** : `/json/evaluate/<periodStart>/<periodEnd>/<periodDiff>/<ticker`

**Usage** : Sililar to main evaluate performance, however with a specific ticker (Facebook : FB) Inputs are: (periodDiff - **accepted in D format**). periodStart **(accepted in YYYY-MM-DD format for both)** and periodEnd, for the period you want to evaluate against **(This usually is up to a maximum of 1 1/2 weeks beind today, as it takes intraday data - limitations of the AlphaVantage API)** 

**Latency** : Up to 10s, can take a long time due to the huge amount of data it has to process on the backend.

**Return** : Returns a true/false whether the sentiment analysis on that article successfully predicted that the stock price would go up/down in + periodDiff days
```javascript
{ 
    true, 
    false,
    true,
    true, 
    true, 
    false
}
```

## Command Sending Endpoints
These endpoints send permanently changing commands to the backend, **use with extreme caution**


### Buy and Sell Stock 
**Endpoint** : `/json/<command>/<ticker>/<price>/<shares>`


**Usage** : Used for either buying or selling shares, has error handling to stop you buying or selling more shares than you can afford or have - Takes in <command> (either "buy" or "sell"), <ticker> (the ticker of the company (e.g. FB)), <price> (the price that you are buying at, usually derived by a call to AlphaVantage), <shares> (the number of shares that you want to buy) 
    
**Latency** : <100ms, writing to db, so very quick

**Return** : Returns a command agreeing that you bought or sold stock, confirming the trade
```javascript
{ 
    "BOUGHT 100 MSFT at 82.1"
}
```
### Reset Portfolio Value 
**Endpoint** : `json/reset/tickerfunds`

**Usage** : **Extremely important function - This will reset all stock owned in the application, and effectively start from a clean slate, only use if you are sure to do this, there are no warnings about whether you are sure**

**Latency** : <100ms

**Return**:
```javascript
{
    true
}
```
