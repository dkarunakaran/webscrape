from bs4 import BeautifulSoup 
import requests 
import pandas as pd
import json
import re
import datefinder
from sqlitedb import SqliteDB
from chroma import ChromaDBConnect
from bs4.element import Comment
import yaml
import time
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import sys

class WebScrape:
    def __init__(self, sql_db, chromadb):
        with open("config.yaml") as f:
            cfg = yaml.load(f, Loader=yaml.FullLoader)
        self.count = 0
        self.url_threshold = cfg['webscrape']['url_threshold']
        self.debug = cfg['webscrape']['debug']
        self.unlock_get_all_urls = cfg['webscrape']['unlock_get_all_urls'] # This has to be set False all the time as we do not need to run that often. May be once in a month.
        self.exceptions = cfg['webscrape']['exceptions']
        self.sql_db = sql_db
        self.chromadb = chromadb

    def get_all_urls(self):
        if self.unlock_get_all_urls == True:
            head_url = 'https://www.ato.gov.au'
            columns = ['url', 'visited', 'update_date', 'processed_first']
            urls_df = pd.DataFrame(columns=columns)
            save_urls_df = pd.DataFrame(columns=columns)
            # Append Dict as row to DataFrame
            new_row = {"url": "https://www.ato.gov.au/individuals-and-families/your-tax-return", "visited": False, 'update_date': None, 'processed_first': False}
            urls_df = pd.concat([urls_df, pd.DataFrame([new_row])], ignore_index=True)
            save_urls_df = pd.concat([save_urls_df, pd.DataFrame([new_row])], ignore_index=True)
            try:
                while urls_df.shape[0] > 0:
                    for index, row in urls_df.iterrows():
                        if row.visited == True:
                            continue
                        site = row.url
                        print(f"Sub pages of {site} and url count {urls_df.shape[0]}")
                    
                        #To avoid connection error we need below than just simple r = requests.get(site) 
                        header = {
                            "User-Agent": 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/105.0.0.0 Safari/537.36'
                        }
                        session = requests.Session()
                        retry = Retry(connect=3, backoff_factor=0.5)
                        adapter = HTTPAdapter(max_retries=retry)
                        session.mount('http://', adapter)
                        session.mount('https://', adapter)
                        html = session.get(site, headers=header).text

                        # Converting the text 
                        soup = BeautifulSoup(html,"html.parser") 
                        temp_url = []
                        new_url_rows = []
                        for i in soup.find_all("a", href=True): 
                            href = i.attrs['href'] 
                            if href.startswith("/") and self.exception_status(href) == False: 
                                site = head_url+href
                                if site not in urls_df.values :
                                    #if save_urls_df['url'].str.contains(site).any() == False and site not in temp_url:
                                    if site not in temp_url:
                                        temp_url.append(site)
                                        new_url_rows.append({"url": site, "visited": False, 'update_date': None, 'processed_first': False})
                        
                        urls_df = pd.concat([urls_df, pd.DataFrame(new_url_rows)], ignore_index=True)
                        save_urls_df = pd.concat([save_urls_df, pd.DataFrame(new_url_rows)], ignore_index=True)
                        row.visited = True
                        urls_df.loc[index] = row
                        
                        # Checking threshold of urls reached
                        if save_urls_df.shape[0] > self.url_threshold:
                            break    

                    # Checking threshold of urls reached
                    if save_urls_df.shape[0] > self.url_threshold:
                        break    
                    
                    urls_df.drop(urls_df.index[(urls_df["visited"] == True)],axis=0,inplace=True)
                    
                    # Remove all duplicates, but keep last duplicate value
                    urls_df = urls_df.drop_duplicates(subset=['url'], keep='last')

                    # Delay 10 seconds to avoid the connection error imposed by the client server
                    time.sleep(10)

            except:
                e = sys.exc_info()[0]
                print(e)
            finally:
                # Remove all duplicates, but keep last duplicate value
                save_urls_df = save_urls_df.drop_duplicates(subset=['url'], keep='last')
                save_urls_df.to_sql('URLs', con=self.sql_db.conn, if_exists='replace', index_label="id")
        else:
            print("This function is blocked from running...")

    def process_urls(self):

        # Run SQL          
        sql_query = pd.read_sql_query('SELECT * FROM URLs', self.sql_db.conn)

        # Convert SQL to DataFrame
        urls_df = pd.DataFrame(sql_query, columns = ['id', 'url', 'update_date', 'processed_first'])

        for index, row in urls_df.iterrows(): 
            site = row.url
            r = requests.get(site) 

            # Converting the text 
            soup = BeautifulSoup(r.text,"html.parser") 
            
            # Getting Last update date if any
            date_time_str = "None"
            p_elem = soup.find_all("p", {"class": "AtoDefaultPageHeader_bottom__date__L4xB4"})
            para = []
            for x in p_elem:
                para.append(str(x))
            if len(para) > 0 and 'Last updated' in para[0]:
                matches = datefinder.find_dates(para[0])
                date = next(matches)
                date_time_str = date.strftime("%d-%m-%Y")
            row.updated_date = date_time_str
            
            if row.processed_first == 0:
                # ^Running for the first time^
                print(f"INSERT---------Processing {site}---------")
                row.processed_first = True
                data = self.get_page_text(soup, site, date_time_str)
                self.chromadb.insert(data)

                # Update the SQL table
                update_statement = "UPDATE URLs SET update_date = ?, processed_first = ? WHERE id = ?"
                self.sql_db.cursor.execute(update_statement, (row.updated_date, row.processed_first, row.id))
                self.sql_db.conn.commit()
            else:
                # ^Not running for the first time^
                print(f"UPDATE---------Processing {site}---------")
                # Check the chroma vector db contains the data and if so, check the update date stored with the current update date fetched to see 
                # whether we need to change the content in the db
                doc = self.chromadb.get(site)
                if self.update_document_status(doc, site, row.updated_date) == True:
                    data = self.get_page_text(soup, site, date_time_str)
                    self.chromadb.update(doc['id'], data)

            urls_df.loc[index] = row

    def update_document_status(self, doc, site, date):
        flag = False
        
        if date != "None" and doc is not None and doc['metadata']['last_updated'] != date:
            flag = True
        
        return flag

    def get_page_text(self, soup, site, date_time_str):
        texts = soup.findAll(string=True)
        visible_texts = filter(self.tag_visible, texts)  
        content = u" ".join(t.strip() for t in visible_texts)
        data = {'url':site, 'last_updated': date_time_str, 'content': content}
        
        return data

    def tag_visible(self, element):
        if element.parent.name in ['style', 'script', 'head', 'title', 'meta', '[document]']:
            return False
        if isinstance(element, Comment):
            return False
        return True
    
    def exception_status(self, href):
        exceptit = False
        for exception in self.exceptions:
            if exception in href: 
                exceptit = True
        return exceptit
    
    # Function to validate URL 
    # using regular expression 
    def isValidURL(self, str):
        # Regex to check valid URL 
        regex = ("((http|https)://)(www.)?" +
                "[a-zA-Z0-9@:%._\\+~#?&//=]" +
                "{2,256}\\.[a-z]" +
                "{2,6}\\b([-a-zA-Z0-9@:%" +
                "._\\+~#?&//=]*)")
        
        # Compile the ReGex
        p = re.compile(regex)
    
        # If the string is empty 
        # return false
        if (str == None):
            return False
    
        # Return if the string 
        # matched the ReGex
        if(re.search(p, str)):
            return True
        else:
            return False

    def __len__(self):
        return len(self.urls)

    def check_update_status(self):
        pass


if __name__=="__main__":
    sql_db = SqliteDB()
    chromadb = ChromaDBConnect() 
    webscrape = WebScrape(sql_db=sql_db, chromadb=chromadb)
    #webscrape.get_all_urls()
    webscrape.process_urls()
    sql_db.conn_close()
    
    

         


