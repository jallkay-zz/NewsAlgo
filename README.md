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
Endpoint : `/json/detail/<id>`


### Article/Report Analysis 
Endpoint : `/json/detail/analysis/<id>`


### Backend Messages 
Endpoint : `json/messages`


### Portfolio Total 
Endpoint : `json/totalall`


### Itemised Portfolio Total 
Endpoint : `json/total`


### Enriched Stock Price 
Endpoint : `json/stock/<type>/<ticker>`


### Evaluate Performance (Whole Portfolio) 
Endpoint : `/json/evaluate/<periodStart>/<periodEnd>/<periodDiff>`


### Evaluate Performance (Specific Company) 
Endpoint : `/json/evaluate/<periodStart>/<periodEnd>/<periodDiff>/<ticker`


## Command Sending Endpoints
These endpoints send permanently changing commands to the backend, **use with extreme caution**


### Buy and Sell Stock 
Endpoint : `/json/<command>/<ticker>/<price>/<shares>`


### Reset Portfolio Value 
Endpoint : `json/reset/tickerfunds`
