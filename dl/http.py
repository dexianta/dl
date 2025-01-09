from fastapi import FastAPI, Form, File, UploadFile, Query, HTTPException
from dl.utils import data, write_data
import dl.utils as utils
from fastapi.responses import HTMLResponse, RedirectResponse
import os
import signal

app = FastAPI()


@app.get("/", response_class=HTMLResponse)
async def login():
    return html_template("", """
        <h1>Welcome to DocLib</h1>
        <form action="/auth" method="post">
        <label for="secret_key">Enter Your Token:</label><br>
        <input type="text" id="token" name="token" required><br>
        <button type="submit">Login</button>
        </form>
    """)


@app.post("/auth", response_class=HTMLResponse)
async def auth(token: str = Form(...)):
    check(token)
    return redirect("/menu", token)


@app.get("/menu", response_class=HTMLResponse)
async def main_menu(token: str = Query(...)):
    check(token)
    return html_template(token, f"""
        <h1>DocLib</h1>
        <ul>
            <li><a href="/files?token={token}">Manage Files</a></li>
            <li><a href="/set-prompt?token={token}">Set Prompt</a></li>
            <li><a href="/chunk-search?token={token}">Search Chunk</a></li>
            <li><a href="/ask-question?token={token}">Ask Question</a></li>
        </ul>
    """)


@app.get("/files", response_class=HTMLResponse)
async def manage_files(token: str = Query(...)):
    check(token)
    global data
    docs_html = "".join(
        f"""<li>
        <form style="display: inline;" action="/delete-file?token={token}" method="post">
            <input type="hidden" name="id" value="{doc.id}">
            <button type="submit">x</button>
        </form>
        <span style="font-weight: bold;">{doc.id}</span>.
        <span style="font-weight: bold;">{doc.title}</span>
    </li>"""
        for doc in data.docs
    )
    return html_template(token, f"""
        <h1> Manage Files</h1>
        <ul> {docs_html} </ul>
         <form id="uploadForm" action="/add-file?token={token}" method="post" enctype="multipart/form-data">
            <label for="file">Add File (Select File):</label><br>
            <input type="file" id="file" name="file" style=""><br>
            <button id="submitButton" type="submit">Add</button>
        </form>
        """)


@app.post("/delete-file")
async def delete_file(id: int = Form(...), token=Query(...)):
    check(token)
    utils.delete_file(id)
    return redirect("/files", token)


@app.post("/add-file")
async def add_file(token=Query(...), file: UploadFile = File(...)):
    check(token)
    # Get the file name
    file_name = file.filename

    # Read the file content as bytes
    file_content = await file.read()

    print('adding file..', 'name: ', file_name, 'bytes: ', len(file_content))

    utils.add_uploaded_file(file_name, file_content)

    return redirect("/files", token)


@app.get("/set-prompt", response_class=HTMLResponse)
async def set_prompt(token: str = Query(...)):
    check(token)
    global data
    return html_template(token,
                         f"""
        <h1>Set Prompt</h1>
        <h3> Current Prompt: </h3>
        <p> {data.state.prompt} </p>
        <form action="/set-prompt-do" method="post">
            <label for="query">Set your new prompt:</label>
            <textarea id="query" name="prompt" rows="5" cols="40"></textarea>
            <button type="submit">Set</button>
        </form>
        <form action="/reset-prompt" method="post">
            <button type="submit">Reset</button>
        </form>
    """
    )


@app.post("/reset-chat", response_class=HTMLResponse)
async def reset_chat(token: str = Query(...)):
    check(token)
    global data
    data.reset_chat(token)
    return redirect("/ask-question", token)


@app.post("/reset-prompt", response_class=HTMLResponse)
async def reset_prompt(token: str = Query(...)):
    check(token)
    global data
    data.reset_prompt(token)
    return redirect("/set-prompt", token)


@app.post("/set-prompt-do", response_class=HTMLResponse)
async def set_prompt_do(prompt: str = Form(...), token: str = Query(...)):
    check(token)
    global data
    data.set_prompt(token, prompt)
    return redirect("/set-prompt", token)


@app.get("/chunk-search", response_class=HTMLResponse)
async def search_chunk(token: str = Query(...)):
    check(token)
    return html_template(token,
                         """
        <h1>Search Chunk</h1>
        <form id="uploadForm" action="/search-results" method="post">
            <label for="query">Enter Search Query:</label>
            <textarea id="query" name="query" rows="5" cols="40"></textarea>
            <button id="submitButton" type="submit">Search</button>
        </form>
    """
                         )


@app.post("/search-results", response_class=HTMLResponse)
async def search_results(token: str = Query(...), query: str = Form(...)):
    check(token)
    ret = utils.search_chunk(query)
    results = [r.str() for r in ret]
    results_html = "".join(f"<li>{result}</li>" for result in results)
    return html_template(token, f"""
        <h1> Search Results </h1>
        <ul style="list-style-type:disc;margin-left: 20px"> {results_html} </ul>
    """)


@app.get("/ask-question", response_class=HTMLResponse)
async def ask_question(token: str = Query(...)):
    chat_html = "".join(f"<p>{msg}</p>" if msg.startswith('sys:') else f'<p style="color: gray;">{msg}</p>'
                        for msg in utils.data.state.chat_history)
    check(token)
    return html_template(token, f"""
    <h1> Ask a Question </h1>
    <div> {chat_html} </div>
    <form id="uploadForm" action="{r("/submit-question", token)}" method="post">
        <label for="query">Enter your question:</label>
        <textarea id="query" name="query" rows="5" cols="40"></textarea>
        <button id="submitButton" type="submit">Search</button>
    </form>
    <form action="{r("/reset-chat", token)}" method="post">
        <button type="submit">reset</button>
    </form>
""")


@app.post("/submit-question", response_class=HTMLResponse)
async def submit_question(query:
                          str = Form(...), token: str = Query(...)):
    check(token)
    answer = utils.ask_question(query)
    utils.data.add_chat(token, "usr: " + query)
    utils.data.add_chat(token, "sys: " + answer)
    return redirect("/ask-question", token)


@app.on_event("shutdown")
def shutdown_event():
    print('saving data..')
    write_data(data)


@app.post("/shutdown")
async def shutdown():
    os.kill(os.getpid(), signal.SIGINT)  # Gracefully shut down


def authed(key:
           str) -> str:
    global data
    return data.state.users[key]


def r(path:
      str, token: str) -> str:
    return f"{path}?token={token}"


def check(token):
    global data
    user = data.get_user(token)
    if user == "":
        raise HTTPException(status_code=401, detail="Unauthorized")


def redirect(path, token):
    return RedirectResponse(r(path, token), status_code=303)


def html_template(token, content):
    return f"""
    <html>
        <head>
            <title>DocLib</title>
            <link href="https://fonts.googleapis.com/css2?family=Roboto:wght@400;700&display=swap" rel="stylesheet">
            <style>
                body {{
                    font-family: 'Roboto', sans-serif;
                    font-size: 24px;
                    line-height: 1.6;
                    margin: 20px;
                    color: #333;
                }}
                h1 {{
                    color: #2c3e50;
                }}
                a, button {{
                    font-weight: bold;
                    color: #2980b9;
                    text-decoration: none;
                    cursor: pointer;
                }}
                a:hover {{
                    text-decoration: underline;
                }}
                ul {{
                    list-style: none;
                    padding: 0;
                }}
                ul li {{
                    margin: 10px 0;
                }}
                button {{
                    background-color: #2980b9;
                    border: none;
                    padding: 10px 15px;
                    color: white;
                    border-radius: 5px;
                    cursor: pointer;
                }}
                button:disabled {{
                background-color: #ccc;
                    color: #666;
                    cursor: not-allowed;
                    opacity: 0.7;
                }}
                button:hover {{
                    background-color: #3498db;
                }}
                form {{
                    margin-top: 20px;
                }}
                input, textarea {{
                    font-family: 'Roboto', sans-serif;
                    padding: 10px;
                    border: 1px solid #ccc;
                    border-radius: 5px;
                    width: 100%;
                    margin-bottom: 10px;
                }}
            </style>
        </head>
        <body>
            {content}
            {script}
        </body>
        <a href="/menu?token={token}">Go Back</a>
    </html>
    """


script = """
<script>
    const query = document.getElementById("query");
    if (query) {
        query.addEventListener('keydown', function(event) {
            if (event.key === 'Enter') {
                event.preventDefault()
                const start = this.selectionStart
                const end = this.selectionEnd
                this.value = this.value.substring(0, start) + "\\n" + this.value.substring(end)
                this.selectionStart = this.selectionEnd = start + 1
            }
        });
    }

    const form = document.getElementById('uploadForm');
    const submitButton = document.getElementById('submitButton');

    if (form && submitButton) {
        form.addEventListener('submit', function(event) {
            event.preventDefault();
            submitButton.disabled = true;
            form.submit()
        });
    }
</script>
"""
