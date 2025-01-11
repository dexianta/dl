from dl.utils import init, write_data, data
from dl.http import app
import uvicorn


def run_server():
    try:
        init()
        uvicorn.run(app, host="127.0.0.1", port=8000)
    except Exception as e:
        print(f'something went wrong: {e}')
        write_data(data)
        return


def main():
    run_server()
