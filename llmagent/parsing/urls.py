import fire
import requests
from bs4 import BeautifulSoup
import os
import urllib.parse
from urllib.parse import urljoin
from rich import print
from rich.prompt import Prompt
from typing import List, Tuple
from pydantic import HttpUrl, ValidationError, BaseModel
import logging

logger = logging.getLogger(__name__)


def get_user_input(msg: str, color: str = "blue") -> str:
    """
    Prompt the user for input.
    Args:
        msg: printed prompt
        color: color of the prompt
    Returns:
        user input
    """
    color_str = f"[{color}]{msg} " if color else msg + " "
    print(color_str, end="")
    return input("")


def get_list_from_user(
    prompt="Enter input (type 'done' or hit return to finish)",
    n=None,
) -> List[str]:
    """
    Prompt the user for inputs.
    Args:
        prompt: printed prompt
        n: how many inputs to prompt for. If None, then prompt until done, otherwise
            quit after n inputs.
    Returns:
        list of input strings
    """
    # Create an empty set to store the URLs.
    input_set = set()

    # Use a while loop to continuously ask the user for URLs.
    i = 0
    while True:
        # Prompt the user for input.
        input_str = Prompt.ask(f"[blue]{prompt}")
        # Check if the user wants to exit the loop.
        if input_str.lower() == "done" or input_str == "":
            break
        input_set.add(input_str.strip())
        i += 1
        if i == n:
            break

    return list(input_set)


class Url(BaseModel):
    url: HttpUrl


def get_urls_and_paths(inputs: List[str]) -> Tuple[List[str], List[str]]:
    """
    Given a list of inputs, return a list of URLs and a list of paths.
    Args:
        inputs: list of strings
    Returns:
        list of URLs, list of paths
    """
    urls = []
    paths = []
    for item in inputs:
        try:
            m = Url(url=item)
            urls.append(m.url)
        except ValidationError:
            if os.path.exists(item):
                paths.append(item)
            else:
                logger.warning(f"{item} is neither a URL nor a path.")
    return urls, paths


def find_urls(
    url="https://en.wikipedia.org/wiki/Generative_pre-trained_transformer",
    visited=None,
    depth=0,
    max_depth=2,
):
    """
    Recursively find all URLs on a given page.
    Args:
        url:
        visited:
        depth:
        max_depth:

    Returns:

    """
    if visited is None:
        visited = set()
    visited.add(url)

    try:
        response = requests.get(url)
        response.raise_for_status()
    except (
        requests.exceptions.HTTPError,
        requests.exceptions.RequestException,
    ):
        print(f"Failed to fetch '{url}'")
        return visited

    soup = BeautifulSoup(response.content, "html.parser")
    links = soup.find_all("a", href=True)

    urls = [urljoin(url, link["href"]) for link in links]  # Construct full URLs

    if depth < max_depth:
        for link_url in urls:
            if link_url not in visited:
                find_urls(link_url, visited, depth + 1, max_depth)

    return visited


def org_user_from_github(url):
    parsed = urllib.parse.urlparse(url)
    org, user = parsed.path.lstrip("/").split("/")
    return f"{org}-{user}"


if __name__ == "__main__":
    # Example usage
    found_urls = set(fire.Fire(find_urls))
    for url in found_urls:
        print(url)
