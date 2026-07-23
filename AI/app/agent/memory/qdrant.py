"""这个是用于连接Qdrant向量数据库的工具"""
import os
from qdrant_client import QdrantClient
from langchain_openai import OpenAIEmbeddings
from langchain_qdrant import QdrantVectorStore

qdrantClient = QdrantClient(
  url= os.getenv("QDRANT_URL")
)


#提供向量模型信息
embeddings = OpenAIEmbeddings(
  model = os.getenv("EMBEDDING_MODEL"),
  api_key= os.getenv("DASHSCOPE_API_KEY"),
  base_url= os.getenv("DASHSCOPE_BASE_URL")
)

#构建向量数据库连接消费商店实体
store = QdrantVectorStore(
  client= qdrantClient,
  collection_name= os.getenv("QDRANT_COLLECTION"),
  embedding= embeddings
)