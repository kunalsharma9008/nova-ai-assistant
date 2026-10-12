from ddgs import DDGS


def web_search(query: str, max_results: int = 5):
    """
    Search the web using DuckDuckGo
    and return clean results for Nova.
    """

    try:
        print(f"WEB SEARCH: {query}")

        results = DDGS().text(
            query,
            max_results=max_results
        )

        formatted_results = []

        for result in results:
            formatted_results.append({
                "title": result.get("title", ""),
                "body": result.get("body", ""),
                "url": result.get("href", "")
            })

        print(f"WEB RESULTS: {len(formatted_results)}")

        return formatted_results

    except Exception as error:
        print("WEB SEARCH ERROR:", error)
        return []