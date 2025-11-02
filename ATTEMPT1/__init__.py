# Make ATTEMPT1 a proper Python package
from .pipeline import EnhancedRAGPipeline
from .config import Config

__all__ = ['EnhancedRAGPipeline', 'Config']