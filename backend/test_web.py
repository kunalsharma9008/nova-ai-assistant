from web_search import web_search

results = web_search("current Prime Minister of India")

for result in results:
    print("\nTITLE:", result["title"])
    print("URL:", result["url"])
    print("INFO:", result["body"])