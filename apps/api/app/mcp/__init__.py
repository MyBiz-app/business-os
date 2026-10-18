"""AI connectors (round 7, R37a): Claude, ChatGPT and other MCP apps read a business directly.

The business owner adds MyBiz as a connector in their own AI app. The app signs in through a small
OAuth 2.1 server (`oauth.py`: dynamic registration, authorization code with PKCE, refresh tokens)
and the person approves in MyBiz, which business it may read. Then it speaks MCP over HTTP to
`/mcp` (`server.py`) and calls the same read tools the built-in assistant uses, as that person,
inside that business, with that person's permissions (`access.py`). Reading only: the request runs
in a read-only database transaction. Every call is counted as usage and limited per business."""
