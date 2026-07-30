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

