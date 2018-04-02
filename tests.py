import unittest
import pandas
import pymongo
import newsAlgo


class TestNewsAlgo(unittest.TestCase):
 
    def setUp(self):
        newsAlgo.stockSymbols = pandas.DataFrame.from_csv('shortListedStocks.csv', header=0)
        client = pymongo.MongoClient(newsAlgo.uri)
        newsAlgo.db = client.get_default_database()
        self.ticker = "FB"
        self.shares = 5
        self.price = 100.00
        self.article = { "title" : "Facebook loses 1 billion pounds after cambridge analytica scandal", 
                   "description" : "the social network is in serious financial troubles now" }

    def test_getCompanyName(self):
        company = newsAlgo.getCompanyName("FB")
        self.assertEqual(company, "Facebook")
 
    def test_getStockSymbol(self):
        ticker = newsAlgo.getStockSymbol("Microsoft")
        self.assertEqual(ticker, "MSFT")
 
    def test_buyStock(self):
        myreturn = newsAlgo.buyStock(self.ticker, self.price, self.shares)
        obj = newsAlgo.db.stocks.find({ "ticker" : self.ticker })[0]
        investedShares  = obj['shares']
        self.assertEqual(type(myreturn), str)
        self.assertEqual(investedShares, self.shares)
    
    def test_sellStock(self):
        objOriginal = newsAlgo.db.stocks.find({ "ticker" : self.ticker })[0]
        initialShares = objOriginal['shares']
        myreturn = newsAlgo.sellStock(self.ticker, self.price, self.shares)
        obj = newsAlgo.db.stocks.find({ "ticker" : self.ticker })[0]
        investedShares  = obj['shares']
        self.assertEqual(type(myreturn), str)
        self.assertEqual(investedShares, initialShares - self.shares)

    def test_getAnalysis(self):
        analysed = newsAlgo.getAnalysis(self.article)
        self.assertEqual(analysed.keys()[0], "Facebook")

    def test_getSentiment(self):
        analysed = newsAlgo.getSentiment(self.article['title'] + ' ' + self.article['description'])
        self.assertEqual(analysed, {"neg" : 0.422, "neu" : 0.578, "pos" : 0.0, "compound" : -0.8176})
 
if __name__ == '__main__':
    unittest.main()