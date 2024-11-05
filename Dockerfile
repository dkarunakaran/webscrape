FROM python:3.12.5-bookworm

RUN pip install --upgrade pip

RUN pip install langchain
RUN pip install langchain-chroma
RUN pip install langchain-ollama
RUN pip install langchain-huggingface

# Database
RUN pip install chromadb==0.5.5
RUN pip install pysqlite3-binary==0.5.3

# Webservices
RUN pip install requests==2.32.3
RUN pip install flask==3.0.3
RUN pip install pandas~=2.1.3

# Web scraping
RUN pip install beautifulsoup4~=4.12.3
RUN pip install datefinder==0.7.3

RUN pip install PyYAML
RUN pip install click
RUN pip install Flask-SQLAlchemy
RUN pip install itsdangerous
RUN pip install Jinja2
RUN pip install MarkupSafe
RUN pip install SQLAlchemy
RUN pip install Werkzeug
RUN pip install scrapy==2.11.2
RUN pip install scrapy-fake-useragent


COPY . /app
WORKDIR /app

CMD ["/bin/bash"]
