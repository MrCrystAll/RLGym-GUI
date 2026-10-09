import multiprocessing

import uvicorn

from app import config
from app.api import app

if __name__ == "__main__":
    multiprocessing.freeze_support()
    uvicorn.run(app, host="127.0.0.1", port=config.PORT)