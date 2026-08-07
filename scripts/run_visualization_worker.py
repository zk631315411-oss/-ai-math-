"""Run the dedicated RQ queue used by the Manim container."""

from multiprocessing import Process

from redis import Redis
from rq import Queue, Worker

from app.config import config


def run_worker() -> None:
    connection = Redis.from_url(config.VISUALIZATION_REDIS_URL)
    queue = Queue(config.VISUALIZATION_QUEUE, connection=connection)
    Worker([queue], connection=connection).work(with_scheduler=True)


if __name__ == "__main__":
    concurrency = config.VISUALIZATION_WORKER_CONCURRENCY
    if concurrency == 1:
        run_worker()
    else:
        workers = [Process(target=run_worker, name=f"manim-worker-{index + 1}") for index in range(concurrency)]
        for worker in workers:
            worker.start()
        try:
            for worker in workers:
                worker.join()
        except KeyboardInterrupt:
            for worker in workers:
                worker.terminate()
            for worker in workers:
                worker.join()
