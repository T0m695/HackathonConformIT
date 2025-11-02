# vector_store.py
import os
import json
import shutil

from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document

from ATTEMPT1.config import Config, logger

from ATTEMPT1.builders import SchemaDocumentBuilder
from ATTEMPT1.bedrock_utils import CachedBedrockEmbeddings

class VectorStoreManager:
    """Manages the vector store for schema documents."""
    
    def __init__(self, schema_path: str = "schema.json"):
        self.schema_path = schema_path
        self.embeddings = CachedBedrockEmbeddings()  # Using a caching wrapper
        self.vectorstore = self._init_vectorstore()
        self.retriever = self.vectorstore.as_retriever(
            search_kwargs={"k": Config.TOP_K_RETRIEVAL}
        )
    
    def _init_vectorstore(self) -> FAISS:
        """Initialize or load vector store"""
        if os.path.isdir(Config.INDEX_DIR):
            logger.info("Loading existing FAISS index...")
            try:
                return FAISS.load_local(
                    folder_path=Config.INDEX_DIR,
                    embeddings=self.embeddings,
                    allow_dangerous_deserialization=True
                )
            except TypeError:
                logger.warning("Using legacy FAISS.load_local (old LangChain version)")
                return FAISS.load_local(
                    folder_path=Config.INDEX_DIR,
                    embeddings=self.embeddings
                )
        else:
            logger.info("Building FAISS index from schema...")
            with open(self.schema_path, "r", encoding="utf-8") as f:
                schema = json.load(f)
            
            docs = SchemaDocumentBuilder.build_documents(schema)
            vectorstore = FAISS.from_documents(docs, self.embeddings)
            vectorstore.save_local(Config.INDEX_DIR)
            logger.info(f"FAISS index saved to {Config.INDEX_DIR}")
            return vectorstore
    
    def retrieve_context(self, query: str) -> str:
        """Get relevant schema context for a query."""
        docs = self.vectorstore.similarity_search(query, k=Config.TOP_K_RETRIEVAL)
        return "\n\n".join([doc.page_content for doc in docs])
    
    def rebuild(self):
        """Rebuild FAISS index from schema"""
        logger.info("Rebuilding FAISS index...")
        
        # Remove old index
        if os.path.isdir(Config.INDEX_DIR):
            shutil.rmtree(Config.INDEX_DIR)
        
        # Rebuild
        with open(self.schema_path, "r", encoding="utf-8") as f:
            schema = json.load(f)
        
        docs = SchemaDocumentBuilder.build_documents(schema)
        self.vectorstore = FAISS.from_documents(docs, self.embeddings)
        self.vectorstore.save_local(Config.INDEX_DIR)
        self.retriever = self.vectorstore.as_retriever(
            search_kwargs={"k": Config.TOP_K_RETRIEVAL}
        )
        
        logger.info("Index rebuilt successfully!")