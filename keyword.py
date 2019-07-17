from pymongo import MongoClient
from konlpy.tag import Hannanum
from konlpy import jvm
import re

client = MongoClient('localhost',27017)
db = client["news"]
collection = db["article"]

jvm.init_jvm()
han = Hannanum()

datas = collection.find()


for data in datas:
    print(data['title'])
    mod_title = re.sub('[^0-9a-zA-Zㄱ-힗]', ' ', data['title'])
    mod_title = mod_title.strip()
    print(han.nouns(u'롯데마트의 흑마늘 양념 치킨'))
