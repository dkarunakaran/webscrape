import scrapy


class ColesSpider(scrapy.Spider):
    name = "coles"
    allowed_domains = ["www.coles.com.au"]
    start_urls = ["https://www.coles.com.au"]

    def parse(self, response):
        pass
