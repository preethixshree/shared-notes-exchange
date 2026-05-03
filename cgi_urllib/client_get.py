"""Client-side HTTP GET example using urllib.

This script requests sample posts from JSONPlaceholder, parses the JSON
response, and prints the first post's title and body.
"""

import json
from urllib.error import HTTPError, URLError
from urllib.request import urlopen


API_URL = "https://jsonplaceholder.typicode.com/posts"


def main():
    try:
        with urlopen(API_URL, timeout=10) as response:
            posts = json.loads(response.read().decode("utf-8"))
    except HTTPError as error:
        print(f"HTTP error: {error.code} {error.reason}")
        return
    except URLError as error:
        print(f"Connection error: {error.reason}")
        return
    except json.JSONDecodeError:
        print("Server returned invalid JSON.")
        return

    if not posts:
        print("No posts found.")
        return

    first_post = posts[0]
    print("First Post")
    print("----------")
    print(f"Title: {first_post.get('title', 'N/A')}")
    print(f"Body: {first_post.get('body', 'N/A')}")


if __name__ == "__main__":
    main()
