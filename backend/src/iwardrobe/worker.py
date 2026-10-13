from arq.worker import run_worker

from .jobs import WorkerSettings

if __name__ == "__main__":
    # Windows' asyncio loop has no Unix signal handlers. The process can still be
    # stopped normally; outstanding leases are recovered by the next worker.
    run_worker(WorkerSettings, handle_signals=False)
