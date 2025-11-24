from pymongo import MongoClient
c=MongoClient('mongodb://localhost:27017/')
db=c['bingo_db']
t=db['tablas']
d=t.find_one({'serial':'CARD00087'},{'_id':0,'serial':1,'won':1,'stateAsigned':1})
print(d)
