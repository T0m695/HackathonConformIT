from sqlsearch import sqlsearch

prompt = input("Prompt: ")
sql_query = sqlsearch(prompt)
print(f"\nSQL: {sql_query}")
