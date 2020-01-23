import multiprocessing as mp
import concurrent.futures as cf
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from selenium.common.exceptions import NoSuchElementException, NoSuchAttributeException, TimeoutException
import urllib.parse
import urllib.request
import requests
from datetime import date, timedelta
import time
from pymongo import MongoClient


# section id 100부터 정치/경제/사회/생활문화/세계/IT과학
# query form : &sectionId=100&date=20190706"

def value_change(value):
    modified = value.replace(',', '')
    return int(modified)


def date_range(start_date, end_date):
    for n in range(int((end_date - start_date).days)):
        yield start_date + timedelta(n)


# 각 섹션 별 최근까지 저장한 날짜를 탐색
def find_recently_date(section_id):
    data = collection.find_one({'section': section_id}, sort=[('month', -1), ('day', -1)])
    day, month = {data['month'], data['day']}
    rd_count = collection.find({'section': section_id, 'month': data['month'], 'day': data['day']}).count()
    if rd_count != 30:
        collection.delete_many({'section': section_id, 'month': data['month'], 'day': data['day']})
    return [day, month]


def create_url(_date, _section_id):
    date_query = "&date=" + _date.strftime("%Y%m%d")
    section_query = "&sectionId={0}".format(_section_id)
    return news_ranking_url + date_query + section_query


def article_processing(section_id):
    with cf.ThreadPoolExecutor() as executor:
        f1 = executor.submit(article_threading, section_id)
        f2 = executor.submit(article_threading, section_id + 1)
    return f1.result() + f2.result()


def article_threading(section_id):
    driver = webdriver.Chrome(chromedriver_path)
    '''
    웹 크롤링 도중에 중단해서 데이터가 중간에 끊겨서 다시 받아와야 한다면
    section 별로 마지막까지 데이터를 저장한 날짜부터 다시 웹 크롤링을 재개하도록
    다음 두 줄 주석 해제
    '''
    r_date = find_recently_date(section_id)
    start_date = date(2019, r_date[0], r_date[1])

    for single_date in date_range(start_date, end_date):
        url = create_url(single_date, section_id)
        get_article_base_info(single_date.year, single_date.month, single_date.day, section_id, url, driver)

    return f'{section_id} end!!\n'


def get_article_base_info(year, month, day, section_id, url, driver):
    driver.get(url)
    driver.implicitly_wait(10)
    soup = BeautifulSoup(driver.page_source, 'html.parser')
    ranking_list = soup.find_all("li", attrs={"class": "ranking_item"})
    for thumb in ranking_list:
        href = thumb.find("a")['href']
        title = thumb.find("a")['title']
        views = thumb.find("div", attrs={"class": "ranking_view"}).text
        press = thumb.find("div", attrs={"class": "ranking_office"}).text
        info = get_article_inner_info(base_news_url + href, driver)
        info["title"] = title
        info["href"] = base_news_url + href
        info["press"] = press
        info["section"] = section_id
        info["views"] = value_change(views)
        info["year"] = year
        info["month"] = month
        info["day"] = day
        print(info)
        collection.insert_one(info)


def get_article_inner_info(article_url, driver):
    # info is dictionary that return article information
    info = {}

    driver.get(article_url)
    try:
        WebDriverWait(driver, 10).until(EC.visibility_of_element_located((By.CLASS_NAME, '_reactionModule')))
        article_html = driver.page_source
        a_soup = BeautifulSoup(article_html, 'html.parser')

        # viewer reaction
        # reaction 순서 좋아요/훈훈해요/슬퍼요/화나요/후속기사 원해요
        a_reaction = a_soup.find("ul", attrs={"class": "u_likeit_layer"})  # reaction panel
        reactions = a_reaction.find_all("span", attrs={"class": "u_likeit_list_count"})
        info["reaction_good"] = value_change(reactions[0].text)
        info["reaction_warm"] = value_change(reactions[1].text)
        info["reaction_sad"] = value_change(reactions[2].text)
        info["reaction_angry"] = value_change(reactions[3].text)
        info["reaction_next"] = value_change(reactions[4].text)
    except TimeoutException:
        try:
            error = driver.find_element_by_class_name('error')
        except NoSuchElementException:
            pass
        else:
            return info

    # move to comment window
    try:
        go_to_comment = driver.find_element_by_class_name('is_navercomment')
    except NoSuchElementException:
        pass
    else:
        go_to_comment.click()
    finally:
        WebDriverWait(driver, 10).until(EC.visibility_of_element_located((By.ID, 'cbox_module')))
        article_html = driver.page_source
        a_soup = BeautifulSoup(article_html, 'html.parser')

    # 총 댓글 수
    try:
        a_comment = a_soup.find("span", attrs={"class": "u_cbox_count"}).text  # comment
        print(a_comment)
    except AttributeError:
        info["comment"] = -1
    else:
        a_comment = a_comment.replace(',', '')
        num_comment = int(a_comment)
        info["comment"] = num_comment

    # 댓글 성별 비율
    try:
        a_chart_sex = a_soup.find("div", attrs={"class": "u_cbox_chart_sex"})
        sex_per = a_chart_sex.find_all("span", attrs={"class": "u_cbox_chart_per"})
    except AttributeError:
        info["male"] = -1
        info["female"] = -1
    else:
        male = sex_per[0].text[:-1]
        female = sex_per[1].text[:-1]
        info["male"] = round(num_comment * int(male) / 100)
        info["female"] = round(num_comment * int(female) / 100)

    # 댓글 나이 비율
    try:
        a_chart_age = a_soup.find("div", attrs={"class": "u_cbox_chart_age"})  # age chart
        age_per = a_chart_age.find_all("span", attrs={"class": "u_cbox_chart_per"})
    except AttributeError:
        info["age_10"] = -1
        info["age_20"] = -1
        info["age_30"] = -1
        info["age_40"] = -1
        info["age_50"] = -1
        info["age_60"] = -1
    else:
        i = 10
        for age in age_per:
            info["age_" + str(i)] = round(num_comment * int(age.text[:-1]) / 100)
            i += 10

    return info


# your mongodb host
client = MongoClient('localhost', 27017)
db = client["news"]
collection = db["article"]
# collection.delete_many({"day":15})

base_news_url = "https://news.naver.com"
news_ranking_url = base_news_url + "/main/ranking/popularDay.nhn?rankingType=popular_day"

chromedriver_path = r'B:\바탕화면\chromedriver.exe'
driver = webdriver.Chrome(chromedriver_path)
# date parameters
start_date = date(2019, 10, 15)
end_date = date(2019, 12, 31) + timedelta(days=1)

if __name__ == '__main__':
    # file = open(r"B:\바탕화면\news_db.txt", "w")
    '''
    #multiprocessing pool 방식
    pool = multiprocessing.Pool(processes=6)
    pool.map(article_processing, range(100, 106))
    
    for i in range(100, 106, 2):
        mp.Process(target=article_processing, args=(i,)).start()
    '''
    # start_time = time.time()
    # with cf.ProcessPoolExecutor() as executor:
    #     for msg in executor.map(article_processing, range(100, 106, 2)):
    #         print(msg)
    # duration = time.time() - start_time
    # print(duration)
    section_id = 105
    for single_date in date_range(start_date, end_date):
        url = create_url(single_date, section_id)
        get_article_base_info(single_date.year, single_date.month, single_date.day, section_id, url, driver)
