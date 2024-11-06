import scrapy
from scrapy.linkextractors import LinkExtractor
from scrapy.http import Request  
from bs4 import BeautifulSoup 
import sys
from bs4.element import Comment
import yaml
from taxinfowebscraping.chroma import ChromaDBConnect
import datefinder
import time

class TaxtinfoSpider(scrapy.Spider):
    name = "taxinfo"
    allowed_domains = ["www.ato.gov.au"]
    start_urls = ["https://www.ato.gov.au/"]
    
    def __init__(self, name=None, **kwargs): 
        super().__init__(name, **kwargs) 
        with open("taxinfowebscraping/config.yaml") as f:
            self.cfg = yaml.load(f, Loader=yaml.FullLoader)
        self.link_extractor = LinkExtractor(unique=True) 
        self.chromadb = ChromaDBConnect()
        self.url_threshold = self.cfg['webscrape']['url_threshold']

    def parse(self, response):
        # For restoring - https://doc.scrapy.org/en/latest/topics/jobs.html
        self.state["items_count"] = self.state.get("items_count", 0) + 1

        soup = BeautifulSoup(response.body,"html.parser") 
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

        site = response.url
        data = self.get_page_text(soup, site, date_time_str)
        doc = self.chromadb.get(site)
        if doc is None:
            # Insert
            self.chromadb.insert(data)
        else:
            # Update
            self.chromadb.update(doc['id'], data)
            
        for link in self.link_extractor.extract_links(response):
            yield Request(link.url, callback=self.parse)
        
        

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
    
    def update_document_status(self, doc, site, date):
        flag = False
        if date != "None" and doc is not None and doc['metadata']['last_updated'] != date:
            flag = True
        
        return flag