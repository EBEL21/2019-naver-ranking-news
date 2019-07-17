from bs4 import BeautifulSoup
from selenium import webdriver
import urllib.parse
import urllib.request
import requests
from datetime import date
import time
import json
from pymongo import MongoClient

#section id 100부터 정치/경제/사회/생활문화/세계/IT과학  
#query form : &sectionId=100&date=20190706"

def get_article_inner_info(article_url):
    #info is dictionary that return article information
    info = {}
    
    driver.get(article_url)
    time.sleep(3)
    article_html = driver.page_source
    a_soup = BeautifulSoup(article_html,'html.parser')
    
    #viewr reaction
    #reaction 순서 GOOD/WARM/SAD/ANGRY/WANT
    a_reaction = a_soup.find("ul", attrs={"class" : "u_likeit_layer"}) # reaction panel
    reactions = a_reaction.find_all("span",attrs={"class" : "u_likeit_list_count"})
    info["reaction_good"] = reactions[0].text
    info["reaction_warm"] = reactions[1].text
    info["reaction_sad"] = reactions[2].text
    info["reaction_angry"] = reactions[3].text
    info["reaction_next"] = reactions[4].text
    

    #move to comment window
    try:
        go_to_comment = driver.find_element_by_class_name('is_navercomment')
    except:
        pass
    else:
        if go_to_comment != None:
            go_to_comment.click()
            time.sleep(3)
            article_html = driver.page_source
            a_soup = BeautifulSoup(article_html,'html.parser')

    #총 댓글 수
    try:
        a_comment = a_soup.find("span", attrs={"class" : "u_cbox_count"}).text #comment
        a_comment = a_comment.replace(',','')
        num_comment = int(a_comment)
        info["comment"] = num_comment
    except:
        pass
    
    #댓글 성별 비율
    try:
        a_chart_sex = a_soup.find("div", attrs={"class" : "u_cbox_chart_sex"}) 
        sex_per = a_chart_sex.find_all("span",attrs={"class" : "u_cbox_chart_per"})
        male = sex_per[0].text[:-1]
        female = sex_per[1].text[:-1]
        info["male"] = round(num_comment * int(male) / 100)
        info["female"] = round(num_comment * int(female) / 100)
    except:
        pass
    
    
    #댓글 나이 비율
    try:
        a_chart_age = a_soup.find("div", attrs={"class" : "u_cbox_chart_age"}) # age chart
        age_per = a_chart_age.find_all("span",attrs={"class" : "u_cbox_chart_per"})

        i = 10
        for age in age_per:
            info["age_"+str(i)] = round(num_comment * int(age.text[:-1]) / 100)
            i += 10
    except:
        pass
    
    return info


client = MongoClient('localhost',27017)
db = client["news"]
collection = db["article"]
#collection.delete_many({"day":15})

base_news_url = "https://news.naver.com"
news_ranking_url = base_news_url + "/main/ranking/popularDay.nhn?rankingType=popular_day"

chromedriver_path = r'B:\바탕화면\chromedriver.exe'
driver = webdriver.Chrome(chromedriver_path)

#date parameters
year = 2019
start_month = 1
end_month = 2

file = open(r"B:\바탕화면\news_db.txt","w")
for month in range(start_month,end_month):
        if month == 12:
            num_days = 31
        else:  
            num_days = (date(year,month+1,1) - date(year,month,1)).days
        for day in range(1,num_days+1):
            date_query = "&date=2019{0:02d}{1:02d}".format(month,day)
            for section_id in range(100,106):
                section_query = "&sectionId={0}".format(section_id)
                query = section_query + date_query
                r = requests.get(news_ranking_url+query)
                soup = BeautifulSoup(r.text,'html.parser')
                ranking_list = soup.find_all("li",attrs={"class" : "ranking_item"})
                for thumb in ranking_list:
                    href = thumb.find("a")['href']
                    title = thumb.find("a")['title']
                    views = thumb.find("div",attrs={"class" : "ranking_view"}).text
                    press = thumb.find("div", attrs={"class" : "ranking_office"}).text
                    info = get_article_inner_info(base_news_url+href)
                    info["title"] = title
                    info["href"] = base_news_url+href
                    info["press"] = press
                    info["section"] = section_id
                    info["views"] = views
                    info["year"] = year
                    info["month"] = month
                    info["day"] = day
                    print(info)
                    collection.insert_one(info)
                

