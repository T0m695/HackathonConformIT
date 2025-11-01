# vector_store.py
import os
import json
import shutil

from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document

from config import Config, logger

from builders import SchemaDocumentBuilder
from bedrock_utils import BedrockEmbeddings

class VectorStoreManager:
    """Manages the vector store for schema documents."""
    
    def __init__(self, schema_path: str = "schema.json"):
        self.schema_path = schema_path
        self.embeddings = BedrockEmbeddings()
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
    
    def retrieve_context(self, question: str) -> str:
        """Retrieve and format relevant context from vector store."""
        docs = self.retriever.get_relevant_documents(question)
        
        # Prioritize examples, then tables, then relationships
        sorted_docs = sorted(docs, key=lambda d: {
            "example": 0,
            "table": 1,
            "column": 2,
            "relationship": 3
        }.get(d.metadata.get("type", "other"), 4))
        
        context = "\n\n".join([
            f"[{doc.metadata.get('type', 'info').upper()}]\n{doc.page_content}"
            for doc in sorted_docs
        ])
        
        logger.info(f"Retrieved {len(docs)} relevant documents")
        logger.debug(f"Schema vector search output (context):\n{context}")  # Added debug logging for schema vector search output
        print("\n🧠 Contexte récupéré de la recherche vectorielle sur le schéma:")  # Added CLI print
        print("─" * 70)
        print(context)
        print("─" * 70)
        
        return context
    
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