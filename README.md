# AK Capital Documentation

Documentation provided here is related to the application hosted at [http://akcapital.herokuapp.com/dashboard]

# Backend API

The API is for use in connecting the backend to the frontend, and therefore is unathenticated due to the scope of the project. 
It allows for direct interaction with the backend, and should be used with extreme caution when sending commands that can permanently affect backend operation. 

All major endpoints are listed below, with an example usage and return

All returns are provided in JSON format, and are prefixed on the server (http://akcapital.herokuapp.com/json/...)

## Data retrieval endpoints
These endpoints are **relatively safe**, and do not perform any lasting effects on the backend

### Headlines 
Endpoint : `/json/headlines/`


### Company-Filtered Headlines 
Endpoint : `/json/headlines/<filter>`


### Quaterly Reports 
Endpoint : `/json/quarterly/`


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
