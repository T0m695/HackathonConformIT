# validators.py
import re
from typing import Tuple, Optional

from .config import Config

class SQLValidator:
    """Validates and sanitizes SQL queries"""
    
    @staticmethod
    def is_safe(sql: str) -> Tuple[bool, Optional[str]]:
        """Check if SQL is safe to execute"""
        sql_upper = sql.upper().strip()
        
        # Check for forbidden operations
        for keyword in Config.FORBIDDEN_SQL_OPERATIONS:
            # Check if keyword appears as a separate word (not part of another word)
            if re.search(rf'\b{keyword}\b', sql_upper):
                return False, f"Forbidden operation: {keyword}"
        
        # Must start with SELECT or WITH (for CTEs)
        if not (sql_upper.startswith("SELECT") or sql_upper.startswith("WITH")):
            return False, "Only SELECT queries are allowed"
        
        # Check for suspicious patterns
        dangerous_patterns = [
            r";\s*(DROP|DELETE|TRUNCATE|ALTER)",
            r"--.*(?:DROP|DELETE)",
            r"/\*.*(?:DROP|DELETE).*\*/"
        ]
        
        for pattern in dangerous_patterns:
            if re.search(pattern, sql_upper):
                return False, "Suspicious pattern detected"
        
        return True, None
    
    @staticmethod
    def extract_sql(text: str) -> str:
        """Extract SQL from LLM response"""
        # Remove markdown code blocks
        if "```" in text:
            parts = text.split("```")
            for part in parts:
                part = part.strip()
                if part.startswith("sql"):
                    part = part[3:].strip()
                # Check if starts with SELECT or WITH
                if part.upper().startswith(("SELECT", "WITH")):
                    return part
        
        # Find first SELECT or WITH statement
        lines = []
        in_sql = False
        
        for line in text.split("\n"):
            line_clean = line.strip()
            
            if line_clean.upper().startswith(("SELECT", "WITH")):
                in_sql = True
            
            if in_sql:
                # Stop on explanation markers
                stop_markers = [
                    "explication:", "note:", "remarque:",
                    "this query", "this will", "explanation:",
                    "---", "###"
                ]
                if any(marker in line_clean.lower() for marker in stop_markers):
                    break
                lines.append(line)
        
        sql = "\n".join(lines).strip()
        
        # Remove trailing semicolons and clean up
        sql = re.sub(r';\s*$', '', sql)
        
        return sql if sql else text.strip()