#!/bin/bash

DIRECTORY=chroma_vectorstore
cd ..

if [ ! -d "$DIRECTORY" ]; then
  echo "$DIRECTORY does not exist."
  mkdir $DIRECTORY
  echo "$DIRECTORY created"
  chmod -R 777 $DIRECTORY
fi

cd webscrape

# Run below step one by one in terminal
sudo docker rmi -f $(sudo docker images -f "dangling=true" -q)
docker run -d --rm --name chromadb -v /home/$(whoami)/Documents/projects/chroma_vectorstore:/chroma/chroma --rm -p 8000:8000 chromadb/chroma:0.5.5
docker build -t webscrape .
docker run --net host --gpus all -it -v /home/$(whoami)/Documents/projects/webscrape:/app webscrape


