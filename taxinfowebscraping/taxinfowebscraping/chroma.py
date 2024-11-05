__import__('pysqlite3')
import sys
sys.modules['sqlite3'] = sys.modules.pop('pysqlite3')

# create the chroma client
from uuid import uuid4
import chromadb
from chromadb.config import Settings
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_chroma import Chroma
from langchain_core.documents import Document
import urllib.parse
import yaml

class ChromaDBConnect:
    def __init__(self):
        with open("taxinfowebscraping/config.yaml") as f:
            self.cfg = yaml.load(f, Loader=yaml.FullLoader)
        self.collection_name = self.cfg['chromadb']['collection_name']
        self.client = chromadb.HttpClient(host=self.cfg['chromadb']['host'], port=self.cfg['chromadb']['port'], settings=Settings(allow_reset=True, anonymized_telemetry=False))
        self.collection = self.client.get_or_create_collection(self.collection_name)
        
        # create the open-source embedding function
        model_name = "sentence-transformers/all-mpnet-base-v2"
        model_kwargs = {'device': 'cpu'}
        encode_kwargs = {'normalize_embeddings': False}
        hf_embed_func = HuggingFaceEmbeddings(
            model_name=model_name,
            model_kwargs=model_kwargs,
            encode_kwargs=encode_kwargs
        )
        
        # tell LangChain to use our client and collection name
        self.db = Chroma(
            client=self.client,
            collection_name=self.collection_name,
            embedding_function=hf_embed_func,
        )
        
        self.total_doc = self.db.get()['ids']
    
    def insert(self, data:list):
        # Reference: https://python.langchain.com/v0.2/docs/integrations/vectorstores/chroma/
        #doc_id = self.total_doc+1
        page_content = data['content']
        metadata={"url": data['url'], 'last_updated': data['last_updated']}

        document = Document(
            page_content=page_content,
            metadata=metadata
        )

        documents = [document]
        uuids = [urllib.parse.quote(data['url'])]
        self.db.add_documents(documents=documents, ids=uuids)
        print("----Inserted----")

    def update(self, uuid:str, data:list):
        page_content = data['content']
        metadata={"url": data['url'], 'last_updated': data['last_updated']}
        updated_document = Document(
            page_content=page_content,
            metadata=metadata
        )
        self.db.update_document(document_id=uuid, document=updated_document)
        print("----Updated----")

    def delete(self, url):
        uuids = [urllib.parse.quote(url)]
        self.db.delete(ids=uuids[0])


    def query(self, query:str):
        docs = self.db.similarity_search(query, k=self.cfg['chromadb']['no_doc_similarity_return'])
        fullcontent =''
        for doc in docs:
            fullcontent ='. '.join([fullcontent,doc.page_content])

        return fullcontent
    
    def get(self, url:str):
        #get function ref: https://python.langchain.com/v0.2/api_reference/chroma/vectorstores/langchain_chroma.vectorstores.Chroma.html#langchain_chroma.vectorstores.Chroma.get
        uuid = urllib.parse.quote(url)
        document = self.db.get(ids=[uuid], limit=1)
        return_data = None
        if len(document['ids']) > 0:
            return_data = {
                'id':document['ids'][0],
                'url':url,
                'metadata':document['metadatas'][0],
                'page_content':document['documents'][0]
            }

        return return_data
    
    

if __name__=="__main__":
    chromadb =ChromaDBConnect()
    #chromadb.add()
    #chromadb.query()
    print(chromadb.get('https://www.ato.gov.au/online-services/online-services-for-individuals-and-sole-traders/ato-app1'))
