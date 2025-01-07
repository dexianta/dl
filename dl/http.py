from fastapi import FastAPI, Form, Request
from dl.utils import docs
from fastapi.responses import HTMLResponse, RedirectResponse
import os
import signal

app = FastAPI()

# Simulate a file list and chat history
file_list = ["file1.txt", "file2.txt", "file3.txt"]
chat_history = []


# Root route: Main menu
@app.get("/", response_class=HTMLResponse)
async def main_menu():
    return html_template(f"""
        <h1>Main Menu</h1>
        <ul>
            <li><a href="/files">Manage Files</a></li>
            <li><a href="/chunk-search">Search Chunk</a></li>
            <li><a href="/ask-question">Ask Question</a></li>
        </ul>
        <form action="/shutdown" method="post">
            <button type="submit">Close Server</button>
        </form>
    """)


# Route to manage files (Docs in this case)
@app.get("/files", response_class=HTMLResponse)
async def manage_files():
    global docs
    docs_html = "".join(
        f"""<li>
        <form style="display: inline;" action="/delete-doc" method="post">
            <input type="hidden" name="id" value="{doc.id}">
            <button type="submit">x</button>
        </form>
        <span style="font-weight: bold;">{doc.id}</span>,
        <span style="font-weight: bold;">{doc.title}</span>
    </li>"""
        for doc in docs.data
    )
    return html_template(f"""
            <h1> Manage Docs </h1>
            <ul> {docs_html} </ul>
            <form action="/add-doc" method="post">
                <label for ="title"> Add Doc (Enter Title): </label>
                <input type="text" id="title" name="title">
                <button type="submit"> Add </button>
            </ form>
            <a href="/"> Go Back </a>""")

# Route: Delete a file


@app.post("/delete-file")
async def delete_file(index: int = Form(...)):
    try:
        del file_list[index]
    except IndexError:
        pass  # Ignore invalid index
    return RedirectResponse("/files", status_code=303)


# Route: Add a file
@app.post("/add-file")
async def add_file(path: str = Form(...)):
    # Just store the path for now
    file_list.append(path)
    return RedirectResponse("/files", status_code=303)


# Route: Search chunk
@app.get("/chunk-search", response_class=HTMLResponse)
async def search_chunk():
    return html_template(f"""
        <h1> Search Chunk </h1>
        <form action="/search-results" method="post">
            <label for ="query"> Enter Search Query: </label>
            <input type="text" id="query" name="query">
            <button type="submit"> Search </button>
        </ form>
        <a href="/"> Go Back </a>
    """)


# Route: Search results
@app.post("/search-results", response_class=HTMLResponse)
async def search_results(query: str = Form(...)):
    # Simulated response
    results = [f"Result {i} for '{query}'" for i in range(1, 6)]
    results_html = "".join(f"<li>{result}</li>" for result in results)
    return html_template(f"""
        <h1> Search Results </h1>
        <ul> {results_html} </ul>
        <a href="/chunk-search"> Go Back </a>
    """)


# Route: Ask question
@app.get("/ask-question", response_class=HTMLResponse)
async def ask_question():
    chat_html = "".join(
        f"<p><strong>{user}:</strong> {message}</p>" for user, message in chat_history)
    return html_template(f"""
        <h1> Ask a Question </h1>
        <div> {chat_html} </div>
        <form action="/submit-question" method="post">
            <input type="text" name="message" placeholder="Type your message">
            <button type="submit"> Send </button>
        </ form>
        <a href="/"> Go Back </a>
    """)


# Route: Submit question
@app.post("/submit-question", response_class=HTMLResponse)
async def submit_question(message: str = Form(...)):
    # Simulate bot response
    chat_history.append(("User", message))
    chat_history.append(("Bot", f"Response to '{message}'"))
    return RedirectResponse("/ask-question", status_code=303)


# Route: Shutdown the server
@app.post("/shutdown")
async def shutdown():
    os.kill(os.getpid(), signal.SIGINT)  # Gracefully shut down

    # Helper: HTML template with modern font


def html_template(content):
    return f"""
    <html>
        <head>
            <title>Minimalistic Tool</title>
            <link href="https://fonts.googleapis.com/css2?family=Roboto:wght@400;700&display=swap" rel="stylesheet">
            <style>
                body {{
                    font-family: 'Roboto', sans-serif;
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
        </body>
    </html>
    """
