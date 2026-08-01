Step one: 
set up the uv environment

```
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

restart the IDE (only if needed)

Step two:
We initialize the uv environment. 

```
uv init
```

Step three: 
create a virtual environment and activate.

```
uv venv
.venv/Script/activate
```

Step four:
adding my OpenAI mcp client connection
```
uv add OpenAI mcp[cli] httpx
```

step five:
create mcp_server and host_client_test files

```
ni mcp_server.py
ni host_client_test.py
```
code mcp_server.py

step six:
if the mcp[cli] gives and issue when running the mcp_server try:

```
pip install --force-reinstall "mcp[cli]"
```