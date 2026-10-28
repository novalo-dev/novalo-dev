"""Rewrite the sponsor lists of README.md from GitHub Sponsors.

Runs in the workflow next to it, with SPONSORS_TOKEN: a classic token of this
account with the read:user scope, the only kind that can read the sponsorships
an account receives. Sponsors who chose to stay private are never listed.
"""
import json
import os
import re
import urllib.request

PAST_LIMIT = 5
QUERY = """
query($after: String) {
  viewer {
    sponsorshipsAsMaintainer(first: 100, after: $after, activeOnly: false, includePrivate: false,
                             orderBy: {field: CREATED_AT, direction: DESC}) {
      pageInfo { hasNextPage endCursor }
      nodes {
        isActive
        privacyLevel
        sponsorEntity {
          ... on User { login avatarUrl url }
          ... on Organization { login avatarUrl url }
        }
      }
    }
  }
}
"""


def fetch():
    token = os.environ["SPONSORS_TOKEN"]
    nodes, after = [], None
    while True:
        body = json.dumps({"query": QUERY, "variables": {"after": after}}).encode()
        request = urllib.request.Request(
            "https://api.github.com/graphql",
            data=body,
            headers={"Authorization": "Bearer " + token, "Content-Type": "application/json"},
        )
        with urllib.request.urlopen(request) as response:
            data = json.load(response)
        if "errors" in data:
            raise SystemExit("GraphQL error: " + json.dumps(data["errors"]))
        page = data["data"]["viewer"]["sponsorshipsAsMaintainer"]
        nodes += page["nodes"]
        if not page["pageInfo"]["hasNextPage"]:
            return nodes
        after = page["pageInfo"]["endCursor"]


def avatars(entities, size):
    return "\n".join(
        '<a href="{url}"><img src="{avatar}&s={px}" width="{size}" height="{size}" alt="{login}" title="{login}"></a>'.format(
            url=e["url"], avatar=e["avatarUrl"], px=size * 2, size=size, login=e["login"]
        )
        for e in entities
    )


def main():
    current, past, seen = [], [], set()
    for node in fetch():
        entity = node.get("sponsorEntity")
        # includePrivate: false already leaves them out; checked again because
        # listing a private sponsor would break the promise made to them.
        if not entity or node.get("privacyLevel") != "PUBLIC" or entity["login"] in seen:
            continue
        seen.add(entity["login"])
        (current if node["isActive"] else past).append(entity)
    # Someone who sponsors again after stopping is current, not past.
    past = [e for e in past if e["login"] not in {c["login"] for c in current}][:PAST_LIMIT]

    if current:
        block = avatars(current, 60)
    else:
        block = "_No sponsors yet - [be the first](https://github.com/sponsors/novalo-dev)!_"
    if past:
        block += "\n\n#### Past sponsors\n\n" + avatars(past, 40)

    readme = open("README.md", encoding="utf-8").read()
    updated = re.sub(
        r"(<!-- sponsors:start -->).*?(<!-- sponsors:end -->)",
        lambda m: m.group(1) + "\n" + block + "\n" + m.group(2),
        readme,
        flags=re.S,
    )
    if updated == readme and "<!-- sponsors:start -->" not in readme:
        raise SystemExit("README.md has no <!-- sponsors:start --> marker")
    open("README.md", "w", encoding="utf-8").write(updated)


main()
